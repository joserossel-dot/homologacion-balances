"""Factoría explícita y reversible para persistencia local o heredada."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, cast

from persistence.contracts import (
    LocalAuditRepository,
    LocalDocumentRepository,
    LocalExecutionRepository,
    LocalKnowledgeRepository,
    LocalProcessPersistence,
    PromotionPolicyRepository,
    LocalReportRepository,
    LocalUserRepository,
)
from persistence.local import (
    FileDocumentRepository,
    FileReportRepository,
    JsonKnowledgeRepository,
    LegacyNeonKnowledgeAdapter,
    LocalProcessPersistenceService,
    SqliteOperationalRepository,
)
from persistence.neon_store import NeonKnowledgeStore
from persistence.local.locking import exclusive_file_lock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_MODES = frozenset({"legacy_neon", "local"})


def _environment_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Valor booleano de persistencia inválido: {value!r}")


@dataclass(frozen=True, slots=True)
class PersistenceSettings:
    mode: str = "legacy_neon"
    local_root: Path | None = None
    catalog_seed: Path = PROJECT_ROOT / "catalogo_maestro.json"
    dictionary_seed: Path = PROJECT_ROOT / "diccionario.json"
    enable_operational_in_legacy: bool = False
    master_bundle_version: str = "embedded"

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None,
    ) -> "PersistenceSettings":
        values = os.environ if environment is None else environment
        mode = values.get("PERSISTENCE_MODE", "legacy_neon").strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(
                f"PERSISTENCE_MODE inválido: {mode!r}. "
                f"Valores permitidos: {', '.join(sorted(VALID_MODES))}."
            )
        root_value = values.get("LOCAL_PERSISTENCE_ROOT", "").strip()
        local_root = Path(root_value).expanduser() if root_value else None
        operational = _environment_bool(
            values.get("ENABLE_OPERATIONAL_PERSISTENCE"), default=False,
        )
        catalog_seed = Path(
            values.get("LOCAL_CATALOG_SEED", str(PROJECT_ROOT / "catalogo_maestro.json"))
        ).expanduser()
        dictionary_seed = Path(
            values.get("LOCAL_DICTIONARY_SEED", str(PROJECT_ROOT / "diccionario.json"))
        ).expanduser()
        settings = cls(
            mode=mode,
            local_root=local_root,
            catalog_seed=catalog_seed,
            dictionary_seed=dictionary_seed,
            enable_operational_in_legacy=operational,
            master_bundle_version=values.get(
                "LOCAL_MASTER_BUNDLE_VERSION", "embedded",
            ).strip() or "embedded",
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"Modo de persistencia inválido: {self.mode!r}")
        local_required = self.mode == "local" or self.enable_operational_in_legacy
        if local_required and self.local_root is None:
            raise ValueError(
                "LOCAL_PERSISTENCE_ROOT es obligatorio para persistencia local u "
                "operacional."
            )
        if self.mode == "local":
            for label, path in (
                ("catálogo", self.catalog_seed),
                ("diccionario", self.dictionary_seed),
            ):
                if not path.is_file():
                    raise FileNotFoundError(f"Semilla de {label} no encontrada: {path}")


@dataclass(frozen=True, slots=True)
class PersistenceBundle:
    knowledge: LocalKnowledgeRepository
    documents: LocalDocumentRepository | None = None
    executions: LocalExecutionRepository | None = None
    audit: LocalAuditRepository | None = None
    users: LocalUserRepository | None = None
    reports: LocalReportRepository | None = None
    promotions: PromotionPolicyRepository | None = None
    processes: LocalProcessPersistence | None = None

    @property
    def operational_enabled(self) -> bool:
        return all((
            self.documents, self.executions, self.audit, self.users,
            self.reports, self.promotions, self.processes,
        ))


def build_persistence(
    settings: PersistenceSettings | None = None,
    *,
    legacy_neon_store: NeonKnowledgeStore | None = None,
) -> PersistenceBundle:
    """Construye adaptadores sin abrir conexiones remotas.

    El modo predeterminado conserva ``NeonKnowledgeStore``. El modo local nunca
    instancia el repositorio Neon.
    """
    selected = settings or PersistenceSettings.from_environment()
    selected.validate()

    if selected.mode == "legacy_neon":
        store = legacy_neon_store or NeonKnowledgeStore()
        knowledge: LocalKnowledgeRepository = LegacyNeonKnowledgeAdapter(store)
        if not selected.enable_operational_in_legacy:
            return PersistenceBundle(knowledge=knowledge)
        return _with_local_operational(knowledge, _required_root(selected))

    root = _required_root(selected)
    knowledge_root = root / "knowledge"
    catalog_path = knowledge_root / "catalogo_maestro.json"
    dictionary_path = knowledge_root / "diccionario.json"
    _copy_seed_if_missing(selected.catalog_seed, catalog_path)
    _copy_seed_if_missing(selected.dictionary_seed, dictionary_path)
    _record_local_seed_state(
        knowledge_root,
        version=selected.master_bundle_version,
        catalog_seed=selected.catalog_seed,
        dictionary_seed=selected.dictionary_seed,
    )
    knowledge = JsonKnowledgeRepository(catalog_path, dictionary_path)
    return _with_local_operational(knowledge, root)


def _with_local_operational(
    knowledge: LocalKnowledgeRepository,
    root: Path,
) -> PersistenceBundle:
    documents = FileDocumentRepository(root / "documents")
    reports = FileReportRepository(root / "reports")
    operational = SqliteOperationalRepository(root / "operational" / "operations.db")
    processes = LocalProcessPersistenceService(
        documents=documents,
        executions=cast(LocalExecutionRepository, operational),
        audit=cast(LocalAuditRepository, operational),
        reports=reports,
    )
    return PersistenceBundle(
        knowledge=knowledge,
        documents=documents,
        executions=cast(LocalExecutionRepository, operational),
        audit=cast(LocalAuditRepository, operational),
        users=cast(LocalUserRepository, operational),
        reports=reports,
        promotions=cast(PromotionPolicyRepository, operational),
        processes=cast(LocalProcessPersistence, processes),
    )


def _required_root(settings: PersistenceSettings) -> Path:
    if settings.local_root is None:
        raise ValueError("LOCAL_PERSISTENCE_ROOT no configurado")
    root = settings.local_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _copy_seed_if_missing(source: Path, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_bytes()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def _record_local_seed_state(
    root: Path,
    *,
    version: str,
    catalog_seed: Path,
    dictionary_seed: Path,
) -> None:
    """Registra semilla inicial o actualización pendiente, sin mezclarla."""
    checksum = hashlib.sha256(
        catalog_seed.read_bytes() + b"\0" + dictionary_seed.read_bytes()
    ).hexdigest()
    state_path = root / "seed-state.json"
    history_path = root / "history" / "seed-history.jsonl"
    lock_path = root / ".seed-state.lock"
    with exclusive_file_lock(lock_path):
        current = None
        if state_path.exists():
            current = json.loads(state_path.read_text(encoding="utf-8"))
        if current and current.get("bundle_checksum") == checksum:
            return
        if history_path.exists():
            last_line = next(
                (line for line in reversed(history_path.read_text(
                    encoding="utf-8",
                ).splitlines()) if line.strip()),
                "",
            )
            if last_line and json.loads(last_line).get("bundle_checksum") == checksum:
                return
        event = {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "bundle_version": version,
            "bundle_checksum": checksum,
            "status": "activated" if current is None else "update_pending",
        }
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if current is None:
            JsonKnowledgeRepository._atomic_json_write(state_path, event)
