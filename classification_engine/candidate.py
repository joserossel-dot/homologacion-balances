"""classification_engine/candidate.py — Generador de candidatos por capas.

`CandidateGenerator` produce candidatos de clasificación a partir de múltiples
capas de evidencia independientes:

  1. `code`           — clasificación por código (ClasificadorCodigo).
  2. `catalog_exact`  — match exacto contra `catalogo_maestro.json`.
  3. `synonyms_exact` — match exacto contra `knowledge_base/account_synonyms.json`.
  4. `synonyms_fuzzy` — match difuso (token-normalizado) contra sinónimos.
  5. `special_rules`  — reglas especiales (special_account_rules.py).
  6. `context`        — refuerzo contextual (DocumentProcessingContextAdapter).
  7. `extractor`      — refuerzo por información del extractor.
  8. `profile`        — refuerzo por perfil documental.

Las capas de refuerzo (context/extractor/profile) NO generan candidatos
nuevos: solo agregan evidencia a candidatos ya existentes. Las capas
proponentes (code/catalog_exact/synonyms_*/special_rules) crean candidatos
y cada una aporta su `EvidenceSource`.

El motor queda 100% desacoplado: las fuentes de conocimiento se inyectan
(loader de datos), nunca se importan directamente dentro de la lógica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from classification_engine.decision import (
    Candidate,
    DocumentProcessingContextAdapter,
    EvidenceSource,
)
from classification_engine.score import CANDIDATE_LAYERS, WeightConfig


# ---------------------------------------------------------------------------
# Cargador de fuentes de conocimiento (inyectado)
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeLoader:
    """Encapsula el acceso a las fuentes de conocimiento reutilizables.

    Solo lee los archivos aprobados en la revisión de arquitectura:
    catalogo_maestro.json y knowledge_base/account_synonyms.json. Si un
    archivo no existe o está corrupto, el loader lo degrada con gracia
    (no rompe el motor) y registra una advertencia.
    """

    catalogo_path: str = "catalogo_maestro.json"
    synonyms_path: str = "knowledge_base/account_synonyms.json"
    catalogo: dict[str, dict[str, Any]] = field(default_factory=dict)
    synonyms: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        import json
        from pathlib import Path

        for attr, path in (
            ("catalogo", self.catalogo_path),
            ("synonyms", self.synonyms_path),
        ):
            p = Path(path)
            if not p.exists():
                self.warnings.append(f"No existe {path}")
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if attr == "synonyms" and isinstance(data, dict):
                    data = data.get("cuentas", {})
                if isinstance(data, dict):
                    setattr(self, attr, data)
                else:
                    self.warnings.append(f"{path} no es un dict")
            except (OSError, ValueError) as exc:
                self.warnings.append(f"Error leyendo {path}: {exc}")

    def account_meta(self, code: str) -> dict[str, Any]:
        """Metadatos del catálogo maestro para un código estándar."""
        return self.catalogo.get(code) or {}

    def synonyms_for(self, code: str) -> dict[str, Any]:
        """Entrada de sinónimos para un código estándar."""
        return self.synonyms.get(code) or {}

    def iter_catalog(self):
        return self.catalogo.items()

    def iter_synonyms(self):
        return self.synonyms.items()

    def is_loaded(self) -> bool:
        return bool(self.catalogo) or bool(self.synonyms)


# ---------------------------------------------------------------------------
# Generador de candidatos
# ---------------------------------------------------------------------------


@dataclass
class CandidateGeneratorConfig:
    """Configuración del generador (límites y banderas por capa)."""

    max_candidates: int = 20
    enable_code: bool = True
    enable_catalog_exact: bool = True
    enable_synonyms_exact: bool = True
    enable_synonyms_fuzzy: bool = True
    enable_special_rules: bool = True
    enable_context: bool = True
    enable_extractor: bool = True
    enable_profile: bool = True


class CandidateGenerator:
    """Genera candidatos por capas a partir de una cuenta y un contexto."""

    def __init__(
        self,
        loader: KnowledgeLoader | None = None,
        config: WeightConfig | None = None,
        gen_config: CandidateGeneratorConfig | None = None,
        normalizer: Any = None,
        clasificador: Any = None,
        reglas_especiales: Any = None,
    ) -> None:
        self._loader = loader or KnowledgeLoader()
        self._config = config or WeightConfig()
        self._gen_config = gen_config or CandidateGeneratorConfig()

        # Dependencias opcionales inyectadas (siempre con fallback seguro).
        if normalizer is None:
            try:
                from account_name_normalizer import AccountNameNormalizer
                normalizer = AccountNameNormalizer()
            except ImportError:  # pragma: no cover - entorno sin normalizador
                normalizer = None
        if clasificador is None:
            try:
                from clasificador_codigo_cuenta import ClasificadorCodigo
                clasificador = ClasificadorCodigo()
            except ImportError:  # pragma: no cover
                clasificador = None
        if reglas_especiales is None:
            try:
                import special_account_rules
                reglas_especiales = special_account_rules
            except ImportError:  # pragma: no cover
                reglas_especiales = None

        self._normalizer = normalizer
        self._clasificador = clasificador
        self._reglas = reglas_especiales

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def generate(
        self,
        account_name: str,
        account_code: Optional[str] = None,
        context: Any = None,
    ) -> list[Candidate]:
        """Genera candidatos con evidencia por capa.

        Args:
            account_name: nombre de la cuenta a clasificar.
            account_code: código original (si el documento lo trae).
            context: DocumentContext, DocumentProcessingContextAdapter o dict
                plano (read-only). None si no hay contexto.
        """
        name = (account_name or "").strip()
        adapter = (
            context
            if isinstance(context, DocumentProcessingContextAdapter)
            else DocumentProcessingContextAdapter(context)
        )

        candidates: dict[str, Candidate] = {}

        def _propose(ev: EvidenceSource, name_str: str, category: str = "", tipo: str = "") -> None:
            """Registra una evidencia proponente en el candidato adecuado."""
            code = ev.code
            if not code:
                return
            cand = candidates.get(code)
            if cand is None:
                meta = self._loader.account_meta(code)
                cand = Candidate(
                    code=code,
                    name=name_str or meta.get("nombre_estandar", ""),
                    category=category or meta.get("categoria", ""),
                    tipo_estado=tipo or meta.get("tipo_estado", ""),
                )
                candidates[code] = cand
            cand.add_evidence(ev)

        # --- Capas proponentes -------------------------------------------
        self._layer_code(account_code, name, _propose)
        self._layer_catalog_exact(name, _propose)
        self._layer_synonyms(name, _propose)
        self._layer_special_rules(name, _propose)

        # --- Capas de refuerzo -------------------------------------------
        # Agregan evidencia a candidatos existentes (no crean candidatos).
        if adapter.has_document_context:
            self._layer_context(adapter, candidates)
        if adapter.extractor_info:
            self._layer_extractor(adapter, candidates)
        if adapter.document_profile:
            self._layer_profile(adapter, candidates)

        # --- Orden estable y límite --------------------------------------
        ranked = sorted(
            candidates.values(),
            key=lambda c: (-len(c.evidence), c.code or ""),
        )
        return ranked[: self._gen_config.max_candidates]

    # ------------------------------------------------------------------
    # Capas proponentes
    # ------------------------------------------------------------------

    def _layer_code(self, account_code: Optional[str], name: str, propose) -> None:
        if not self._gen_config.enable_code or not self._clasificador or not account_code:
            return
        try:
            result = self._clasificador.clasificar(account_code)
        except Exception:  # noqa: BLE001 - capa defensiva
            return
        if result is None:
            return
        propose(
            EvidenceSource(
                layer="code",
                code=result.codigo_estandar,
                score=float(result.confianza),
                weight=self._config.weight("code"),
                source="clasificador_codigo_cuenta",
                detail=result.razon,
                matched_value=account_code,
            ),
            name,
        )

    def _layer_catalog_exact(self, name: str, propose) -> None:
        if not self._gen_config.enable_catalog_exact or not name:
            return
        key = self._norm_key(name)
        if not key:
            return
        for code, meta in self._loader.iter_catalog():
            if meta.get("codigo_estandar") != code:
                continue
            nombre_estandar = meta.get("nombre_estandar", "")
            if not nombre_estandar:
                continue
            if self._norm_key(nombre_estandar) == key:
                propose(
                    EvidenceSource(
                        layer="catalog_exact",
                        code=code,
                        score=1.00,
                        weight=self._config.weight("catalog_exact"),
                        source="catalogo_maestro.json",
                        detail=f"Nombre normalizado idéntico a '{nombre_estandar}'",
                        matched_value=nombre_estandar,
                    ),
                    nombre_estandar,
                    category=meta.get("categoria", ""),
                    tipo=meta.get("tipo_estado", ""),
                )
                break

    def _layer_synonyms(self, name: str, propose) -> None:
        if not name:
            return
        exact = self._gen_config.enable_synonyms_exact
        fuzzy = self._gen_config.enable_synonyms_fuzzy
        if not exact and not fuzzy:
            return

        norm_name = self._norm_key(name)
        token_name = self._token_key(name)

        for code, entry in self._loader.iter_synonyms():
            candidates_terms: list[str] = []
            for field in ("sinonimos", "abreviaciones", "errores_ocr",
                          "errores_digitacion", "variantes"):
                vals = entry.get(field) or []
                if isinstance(vals, list):
                    candidates_terms.extend(str(v) for v in vals if str(v).strip())

            official = entry.get("nombre_oficial", "")
            for term in candidates_terms:
                term = str(term).strip()
                if not term:
                    continue
                # Match exacto normalizado
                if exact and self._norm_key(term) == norm_name:
                    propose(
                        EvidenceSource(
                            layer="synonyms_exact",
                            code=code,
                            score=0.95,
                            weight=self._config.weight("synonyms_exact"),
                            source="account_synonyms.json",
                            detail=f"Sinónimo exacto '{term}'",
                            matched_value=term,
                        ),
                        official,
                    )
                # Match difuso por tokens
                elif fuzzy and self._fuzzy_match(term, token_name):
                    propose(
                        EvidenceSource(
                            layer="synonyms_fuzzy",
                            code=code,
                            score=self._config.fuzzy_threshold,
                            weight=self._config.weight("synonyms_fuzzy"),
                            source="account_synonyms.json",
                            detail=f"Sinónimo difuso '{term}'",
                            matched_value=term,
                        ),
                        official,
                    )

    def _layer_special_rules(self, name: str, propose) -> None:
        if not self._gen_config.enable_special_rules or not self._reglas:
            return
        try:
            regla = self._reglas.aplicar_reglas_especiales(name)
        except Exception:  # noqa: BLE001 - capa defensiva
            return
        if not regla or not regla.get("codigo"):
            return
        confianza = float(regla.get("confianza", 0.0))
        propose(
            EvidenceSource(
                layer="special_rules",
                code=regla["codigo"],
                score=confianza,
                weight=self._config.weight("special_rules"),
                source="special_account_rules.py",
                detail=regla.get("explicacion") or regla.get("concepto", ""),
                matched_value=regla.get("nombre", ""),
            ),
            name,
        )

    # ------------------------------------------------------------------
    # Capas de refuerzo
    # ------------------------------------------------------------------

    def _layer_context(self, adapter: DocumentProcessingContextAdapter,
                       candidates: dict[str, Candidate]) -> None:
        """Refuerza candidatos compatibles con el tipo de estado del doc."""
        tipo = adapter.tipo_estado
        if not tipo:
            return
        for cand in candidates.values():
            if cand.tipo_estado == tipo:
                cand.add_evidence(
                    EvidenceSource(
                        layer="context",
                        code=cand.code,
                        score=0.80,
                        weight=self._config.weight("context"),
                        source="DocumentProcessingContext",
                        detail=(
                            f"Documento {adapter.document_type or adapter.family or 'desconocido'} "
                            f"sugiere tipo_estado '{tipo}'"
                        ),
                        matched_value=adapter.document_type or adapter.family or "",
                    )
                )

    def _layer_extractor(self, adapter: DocumentProcessingContextAdapter,
                         candidates: dict[str, Candidate]) -> None:
        """Refuerzo genérico por extractor seleccionado (sin proponer códigos)."""
        parser = adapter.selected_parser or ""
        if not parser:
            return
        boost = 0.20
        for cand in candidates.values():
            cand.add_evidence(
                EvidenceSource(
                    layer="extractor",
                    code=cand.code,
                    score=boost,
                    weight=self._config.weight("extractor"),
                    source="DocumentProcessingContext",
                    detail=f"Extractor '{parser}' activo para el documento",
                    matched_value=parser,
                )
            )

    def _layer_profile(self, adapter: DocumentProcessingContextAdapter,
                       candidates: dict[str, Candidate]) -> None:
        """Refuerzo genérico por perfil documental (family/layout)."""
        family = adapter.family or ""
        layout = adapter.layout or ""
        if not family and not layout:
            return
        boost = 0.20
        for cand in candidates.values():
            cand.add_evidence(
                EvidenceSource(
                    layer="profile",
                    code=cand.code,
                    score=boost,
                    weight=self._config.weight("profile"),
                    source="DocumentProcessingContext",
                    detail=f"Perfil: family={family or '-'}, layout={layout or '-'}",
                    matched_value=f"{family}|{layout}",
                )
            )

    # ------------------------------------------------------------------
    # Utilidades de normalización / matching
    # ------------------------------------------------------------------

    def _norm_key(self, text: str) -> str:
        if not self._normalizer:
            return text.strip().lower()
        try:
            return self._normalizer.normalizar(
                text, expandir_abreviaciones=True, plural=False
            ).strip()
        except Exception:  # noqa: BLE001 - defensivo
            return text.strip().lower()

    def _token_key(self, text: str) -> str:
        if not self._normalizer:
            return text.strip().lower()
        try:
            return self._normalizer.normalizar(
                text, expandir_abreviaciones=True, plural=True, quitar_stopwords=True
            ).strip()
        except Exception:  # noqa: BLE001 - defensivo
            return text.strip().lower()

    def _fuzzy_match(self, term: str, token_name: str) -> bool:
        """Match difuso simple: normaliza ambos y compara claves normalizadas.

        Deterministivo y sin dependencias externas: ambos textos se pasan por
        el normalizador (plural, stopwords) y se comparan iguales. Si el
        normalizador no está disponible, compara tokens en común.
        """
        token_term = self._token_key(term)
        if token_term and token_term == token_name:
            return True
        if not token_name or not token_term:
            return False
        # Fallback: intersección de tokens significativos
        name_tokens = set(token_name.split())
        term_tokens = set(token_term.split())
        if not name_tokens or not term_tokens:
            return False
        overlap = len(name_tokens & term_tokens)
        return overlap / max(len(name_tokens), len(term_tokens)) >= 0.7
