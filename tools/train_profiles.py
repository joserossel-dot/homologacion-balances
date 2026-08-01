"""Entrenador de perfiles de extracción (Sprint 35).

Recorre las 23 familias del conocimiento documental
(`knowledge_base/document_mining.json`), aprende un `TableProfile` por
familia a partir de los balances existentes y valida cobertura/precisión.

    python3 -m tools.train_profiles [--families cluster_xxx] [--max-docs N]

NO modifica el Parser Universal ni el pipeline: solo genera perfiles JSON
que el Sprint 36 (GenericTableExtractor) consumirá.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from document_intelligence.knowledge.fingerprint import extract_preview_lines
from document_intelligence.trainer import (
    ProfileRepository,
    ProfileValidator,
    TableProfile,
    TableProfileTrainer,
)

KNOWLEDGE = Path("knowledge_base")
MINING_JSON = KNOWLEDGE / "document_mining.json"
PROFILES_JSON = KNOWLEDGE / "extractor_profiles.json"
PROFILES_DIR = KNOWLEDGE / "extractor_profiles"
REPORT_MD = Path("reports") / "extractor_trainer_report.md"


def cargar_mining() -> dict:
    if not MINING_JSON.exists():
        raise SystemExit(f"No existe {MINING_JSON}; ejecuta el pipeline de mining.")
    return json.loads(MINING_JSON.read_text(encoding="utf-8"))


def nombre_familia(mining: dict, family_id: str) -> str:
    for rec in mining.get("recommendations", []):
        if rec.get("family_id") == family_id:
            return rec.get("family_name") or rec.get("top_company") or family_id
    for fam in mining["families"]:
        if fam["id"] == family_id and fam.get("top_company"):
            return fam["top_company"]
    return family_id


def leer_documento(path: Path) -> list[str] | None:
    """Devuelve las líneas de texto nativas del documento o None si falla."""
    try:
        lines = extract_preview_lines(str(path))
    except Exception:  # noqa: BLE001 — documento ilegible
        return None
    if not lines:
        return None
    return lines


def entrenar_familia(family: dict, name: str, datasets_dir: str | Path,
                     max_docs: int | None) -> tuple[TableProfile, dict]:
    datasets_dir = Path(datasets_dir)
    docs: list[list[str]] = []
    skipped = 0
    for rel in family.get("files", []):
        if max_docs is not None and len(docs) >= max_docs:
            break
        path = datasets_dir / rel
        if not path.exists():
            skipped += 1
            continue
        lines = leer_documento(path)
        if lines is None:
            skipped += 1
            continue
        docs.append(lines)

    trainer = TableProfileTrainer()
    profile = trainer.train(family["id"], name, docs)

    if docs:
        validator = ProfileValidator(trainer)
        profile.validation = validator.validate(profile, docs)

    return profile, {"docs_total": len(family.get("files", [])),
                     "docs_parseables": len(docs), "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenador de perfiles (Sprint 35)")
    parser.add_argument("--families", nargs="*", default=None,
                        help="Solo estas familias (cluster_xxx)")
    parser.add_argument("--max-docs", type=int, default=None,
                        help="Máximo de documentos por familia")
    args = parser.parse_args()

    mining = cargar_mining()
    datasets_dir = mining.get("datasets_dir", "datasets")

    familias = mining["families"]
    if args.families:
        ids = set(args.families)
        familias = [f for f in familias if f["id"] in ids]
        if not familias:
            raise SystemExit("Ninguna familia coincide con --families.")

    perfiles: dict[str, TableProfile] = {}
    t0 = time.time()

    for i, family in enumerate(familias, 1):
        fid = family["id"]
        name = nombre_familia(mining, fid)
        print(f"[{i}/{len(familias)}] {name} ({fid}) ...", flush=True)
        profile, stats = entrenar_familia(family, name, datasets_dir, args.max_docs)
        perfiles[fid] = profile
        val = profile.validation or {}
        print(
            f"    docs {profile.n_documents}/{profile.docs_total} "
            f"(parseables {stats['docs_parseables']}) "
            f"| layout={profile.layout} code={profile.code_pattern} "
            f"| cols={len(profile.columns)} "
            f"| cobertura={val.get('coverage', 0.0):.2f} "
            f"precisión={val.get('precision', 0.0):.2f}",
            flush=True,
        )

    repo = ProfileRepository(PROFILES_JSON)
    repo.save(perfiles)
    repo.save_individual(perfiles, PROFILES_DIR)
    report = repo.write_report(perfiles, REPORT_MD)

    print("\nPerfiles generados:", len(perfiles))
    print("JSON:", PROFILES_JSON)
    print("Por familia:", PROFILES_DIR)
    print("Reporte:", report)
    print(f"Tiempo total: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
