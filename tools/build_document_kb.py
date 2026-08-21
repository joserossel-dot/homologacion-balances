"""build_document_kb.py — Constructor del Document Knowledge Base (Sprint 32).

Recorre datasets/, genera fingerprints, agrupa en clusters, crea perfiles,
guarda el repositorio JSON y produce document_kb_report.md.

Uso:
    python tools/build_document_kb.py [--datasets datasets] [--limit N]
                                      [--threshold 70] [--out OUT]
                                      [--report REPORT] [--quiet]

También importable: build_kb(...) devuelve (DocumentKnowledgeBase, report_dict).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from document_intelligence import FormatAnalyzer
from document_intelligence.factory import ExtractorFactory, ExtractorType
from document_intelligence.knowledge import (
    DocumentFingerprint,
    DocumentKnowledgeBase,
    DocumentProfile,
    cluster_fingerprints,
)
from document_intelligence.knowledge.fingerprint import extract_preview_lines

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASETS = BASE_DIR / "datasets"
DEFAULT_OUT = BASE_DIR / "knowledge_base" / "document_kb.json"
DEFAULT_REPORT = BASE_DIR / "reports" / "document_kb_report.md"

# Palabras que NO forman parte del nombre de empresa (vienen del formato).
_FORMAT_TOKENS = {
    "balance", "balances", "tributario", "tributarios", "clasificado",
    "clasificados", "individual", "consolidado", "estado", "resultados",
    "resultado", "general", "eeff", "ejercicio", "final", "finales", "original",
    "corregido", "hoja", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
    "de", "del", "el", "la", "los", "las", "y", "al", "a", "anexo", "diciembre",
}
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_RUT_RE = re.compile(r"^rut", re.IGNORECASE)


def guess_company(filename: str, signature_company: str = "") -> str:
    """Mejor esfuerzo para extraer el nombre de empresa de un archivo."""
    name = Path(filename).stem
    tokens = []
    for tok in name.split():
        clean = tok.strip(" ._-")
        if not clean:
            continue
        low = clean.lower()
        if _YEAR_RE.match(clean):
            continue
        if low in _FORMAT_TOKENS:
            continue
        if len(clean) <= 2:
            continue
        tokens.append(clean)
    company = " ".join(tokens)

    # Fallback: usar la razón social del signature si parece real.
    if not company and signature_company and not _RUT_RE.match(signature_company):
        company = signature_company.strip()
    return company or "DESCONOCIDO"


def _file_key(path: Path) -> str:
    return f"{path.name}:{path.stat().st_size}"


def build_kb(
    datasets_dir: str | Path = DEFAULT_DATASETS,
    limit: Optional[int] = None,
    threshold: float = 70.0,
    out_path: str | Path = DEFAULT_OUT,
    report_path: str | Path = DEFAULT_REPORT,
    quiet: bool = False,
) -> tuple[DocumentKnowledgeBase, dict[str, Any]]:
    """Construye la DKB completa: fingerprints → clusters → perfiles → report."""
    root = Path(datasets_dir)
    if not root.exists():
        raise FileNotFoundError(f"Directorio de datasets no encontrado: {root}")

    t0 = time.perf_counter()
    archivos = sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in (".pdf", ".xls", ".xlsx", ".xlsm")
        and "desktop.ini" not in p.name.lower()
    )
    if limit:
        archivos = archivos[:limit]

    analyzer = FormatAnalyzer()
    factory = ExtractorFactory()
    fingerprints: list[DocumentFingerprint] = []
    file_meta: list[dict[str, Any]] = []
    errores = 0

    for path in archivos:
        try:
            lines = extract_preview_lines(path)
            signature = analyzer.analyze(lines)
            fp = DocumentFingerprint.build(signature, lines)
            if path.suffix.lower() == ".pdf" and signature.page_count <= 1:
                try:
                    import pdfplumber
                    with pdfplumber.open(str(path)) as pdf:
                        signature.page_count = len(pdf.pages)
                except Exception:
                    pass
                fp.page_count = signature.page_count

            company = guess_company(path.name, signature.company_name)
            extractor = factory.decide_parser(signature)
            fingerprints.append(fp)
            file_meta.append({
                "file": str(path.relative_to(root)) if root in path.parents else path.name,
                "company": company,
                "family": signature.family.value,
                "extractor": extractor.value,
                "document_type": signature.document_type.value,
            })
            if not quiet:
                print(f"  {path.name}: {signature.family.value} / {extractor.value}")
        except Exception as exc:  # noqa: BLE001
            errores += 1
            if not quiet:
                print(f"  ERROR {path.name}: {exc}")

    # Clustering
    clusters = cluster_fingerprints(fingerprints, threshold=threshold)

    # Perfiles: uno por cluster, con metadatos de empresas/variantes.
    kb = DocumentKnowledgeBase(out_path)
    for cluster in clusters:
        metas = [
            m for m, fp in zip(file_meta, fingerprints)
            if fp.signature_hash == cluster.centroid.signature_hash
        ]
        if not metas:
            # Buscar por pertenencia al cluster.
            cluster_hashes = {m.signature_hash for m in cluster.members}
            metas = [
                m for m, fp in zip(file_meta, fingerprints)
                if fp.signature_hash in cluster_hashes
            ]

        companies = Counter(m["company"] for m in metas)
        files = [m["file"] for m in metas]
        families = Counter(m["family"] for m in metas)
        extractors = Counter(m["extractor"] for m in metas)

        top_company = companies.most_common(1)[0][0] if companies else "DESCONOCIDO"
        family = families.most_common(1)[0][0] if families else "DESCONOCIDO"
        extractor = extractors.most_common(1)[0][0] if extractors else ExtractorType.UNKNOWN.value

        variants = [
            {"company": c, "count": n}
            for c, n in companies.most_common(8)
        ]
        known_variant_names = [v["company"] for v in variants]

        times = len(cluster.members)
        # 'first_seen'/'last_seen': estimados desde el nombre del archivo.
        fechas = [_year_from_name(f) for f in files]
        fechas = [f for f in fechas if f]
        first_seen = min(fechas) if fechas else ""
        last_seen = max(fechas) if fechas else ""

        profile = DocumentProfile(
            id=cluster.id,
            name=f"Formato {top_company}" if top_company != "DESCONOCIDO"
            else f"Formato {family}",
            company=top_company,
            family=family,
            description=(
                f"{cluster.centroid.layout} · {cluster.centroid.code_pattern} "
                f"· {cluster.centroid.document_type} — {times} documento(s)"
            ),
            fingerprint=cluster.centroid,
            known_variants=known_variant_names,
            recommended_extractor=extractor,
            first_seen=first_seen,
            last_seen=last_seen,
            times_seen=times,
            confidence=round(cluster.confidence / 100.0, 4),
            metadata={
                "variants": variants,
                "files": files,
                "companies": list(companies),
                "cluster_members": len(cluster.members),
            },
        )
        kb.add(profile)

    kb.save(out_path)
    stats = kb.statistics()

    report = {
        "datasets_dir": str(root),
        "files_processed": len(archivos),
        "errors": errores,
        "threshold": threshold,
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
        "clusters": len(clusters),
        "statistics": stats,
    }
    _write_report(report, kb, report_path)

    if not quiet:
        print(f"\n✓ DKB guardada en {out_path}")
        print(f"✓ Report en {report_path}")
        print(f"  Archivos procesados: {len(archivos)} (errores: {errores})")
        print(f"  Clusters: {len(clusters)}")
        print(f"  Perfiles: {stats['total_profiles']}")
        print(f"  Variantes: {stats['total_variants']}")
        print(f"  Formatos únicos: {stats['unique_formats']}")
        print(f"  Tiempo: {report['elapsed_seconds']}s")

    return kb, report


def _year_from_name(file_name: str) -> str:
    m = _YEAR_RE.search(file_name)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# Report markdown
# ---------------------------------------------------------------------------

def _write_report(report: dict[str, Any], kb: DocumentKnowledgeBase, report_path) -> None:
    stats = report["statistics"]
    lines: list[str] = []
    lines.append("# Document Knowledge Base — Report")
    lines.append("")
    lines.append(f"Generado: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Datasets: `{report['datasets_dir']}`")
    lines.append(f"Archivos procesados: **{report['files_processed']}** "
                 f"(errores: {report['errors']})")
    lines.append(f"Umbral de clustering: {report['threshold']}")
    lines.append(f"Tiempo: {report['elapsed_seconds']}s")
    lines.append("")

    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---|---|")
    lines.append(f"| Clusters detectados | {report['clusters']} |")
    lines.append(f"| Perfiles totales | {stats['total_profiles']} |")
    lines.append(f"| Variantes totales | {stats['total_variants']} |")
    lines.append(f"| Documentos catalogados | {stats['total_documents']} |")
    lines.append(f"| Formatos únicos | {stats['unique_formats']} |")
    lines.append(f"| Formatos desconocidos | {stats['unknown_formats_count']} |")
    lines.append(f"| Confianza promedio | {stats['avg_confidence']} |")
    lines.append("")

    lines.append("## Top Empresas")
    lines.append("")
    lines.append("| Empresa | Documentos |")
    lines.append("|---|---|")
    for item in stats["top_companies"]:
        lines.append(f"| {item['name']} | {item['count']} |")
    lines.append("")

    lines.append("## Top Familias")
    lines.append("")
    lines.append("| Familia | Documentos |")
    lines.append("|---|---|")
    for item in stats["top_families"]:
        lines.append(f"| {item['name']} | {item['count']} |")
    lines.append("")

    lines.append("## Distribución de Layouts")
    lines.append("")
    lines.append("| Layout | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["layout_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")

    lines.append("## Distribución de Patrones")
    lines.append("")
    lines.append("| Patrón código | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["code_pattern_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")
    lines.append("| Patrón numérico | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["numeric_pattern_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")

    lines.append("## Top Fingerprints Repetidos")
    lines.append("")
    lines.append("| Hash | Veces | Perfiles |")
    lines.append("|---|---|---|")
    for item in stats["repeated_fingerprints"][:10]:
        lines.append(f"| `{item['signature_hash'][:12]}…` | {item['times_seen']} "
                     f"| {', '.join(item['profiles'][:3])} |")
    lines.append("")

    lines.append("## Formatos Desconocidos")
    lines.append("")
    if stats["unknown_formats_count"]:
        lines.append(f"Total: **{stats['unknown_formats_count']}** perfiles con familia DESCONOCIDO.")
        lines.append("")
        for p in stats["unknown_formats"][:20]:
            lines.append(f"- `{p['name']}` — {p['fingerprint']['layout']} "
                         f"· {p['fingerprint']['code_pattern']}")
    else:
        lines.append("Ninguno.")
    lines.append("")

    lines.append("## Catálogo de Perfiles")
    lines.append("")
    lines.append("| ID | Perfil | Empresa | Familia | Layout | Extractor | Veces | Variantes |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for p in sorted(kb.profiles, key=lambda pp: -pp.times_seen):
        lines.append(
            f"| `{p.id}` | {p.name} | {p.company} | {p.family} | "
            f"{p.fingerprint.layout} | {p.recommended_extractor} | "
            f"{p.times_seen} | {len(p.known_variants)} |"
        )
    lines.append("")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye la DKB documental")
    parser.add_argument("--datasets", type=str, default=str(DEFAULT_DATASETS))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=70.0)
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--report", type=str, default=str(DEFAULT_REPORT))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    build_kb(
        datasets_dir=args.datasets,
        limit=args.limit,
        threshold=args.threshold,
        out_path=args.out,
        report_path=args.report,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
