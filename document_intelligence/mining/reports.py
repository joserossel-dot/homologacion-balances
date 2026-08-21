"""Reportes del mining + Quality Analyzer (Sprint 33).

Orquesta el análisis completo:

  1. Matriz de similitud (Top-K vecinos)
  2. Detección de familias (solo fingerprint)
  3. Selección de representantes
  4. Cobertura Top 5/10/20/30
  5. Quality analyzer (familias sospechosas)
  6. Recomendación automática del próximo extractor
  7. Dashboard markdown + CSVs + JSON

NO modifica nada del pipeline de homologación.
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from .coverage import CoverageResult, coverage_by_top_families
from .family_detector import DocumentFamily, detect_families
from .representative_selector import Representative, select_representatives
from .similarity_matrix import (
    DocumentRecord,
    SimilarityMatrix,
    build_similarity_matrix,
    fingerprint_similarity,
)

QUALITY_MIN_SIMILARITY = 70.0
QUALITY_MIN_COUNT = 5
NEAR_IDENTICAL_SIMILARITY = 90.0


# ---------------------------------------------------------------------------
# Quality Analyzer
# ---------------------------------------------------------------------------

def detect_quality_issues(
    families: list[DocumentFamily],
    matrix: Optional[SimilarityMatrix] = None,
) -> list[dict[str, Any]]:
    """Detecta familias sospechosas.

    Tipos de problema:

      - singleton:        familia de un solo documento
      - heterogeneous:    similitud promedio intra-familia < umbral
      - low_confidence:   confianza < 0.6
      - inconsistent_layout: la familia mezcla varios layouts
      - near_identical_split: fingerprints casi idénticos (≥ 90) que
        quedaron separados en familias distintas
    """
    issues: list[dict[str, Any]] = []
    by_id = {f.id: f for f in families}

    for family in families:
        if family.count <= 1:
            issues.append({
                "kind": "singleton",
                "severity": "media",
                "family_id": family.id,
                "message": f"Familia de un solo documento "
                           f"({family.top_company or family.dominant_layout}).",
                "detail": {"count": family.count},
            })

        if family.avg_similarity < QUALITY_MIN_SIMILARITY:
            issues.append({
                "kind": "heterogeneous",
                "severity": "alta",
                "family_id": family.id,
                "message": (
                    f"Cluster heterogéneo: similitud promedio {family.avg_similarity:.0f}% "
                    f"con {family.count} documentos."
                ),
                "detail": {"avg_similarity": family.avg_similarity, "count": family.count},
            })

        if family.confidence < 0.6:
            issues.append({
                "kind": "low_confidence",
                "severity": "media",
                "family_id": family.id,
                "message": (
                    f"Confianza baja ({family.confidence:.2f}) "
                    f"para {family.count} documento(s)."
                ),
                "detail": {"confidence": family.confidence, "count": family.count},
            })

        layouts = {d.fingerprint.layout for d in family.documents
                   if d.fingerprint.layout not in ("", "DESCONOCIDO")}
        if len(layouts) > 1:
            issues.append({
                "kind": "inconsistent_layout",
                "severity": "media",
                "family_id": family.id,
                "message": (
                    f"Layouts inconsistentes dentro de la familia: {sorted(layouts)}."
                ),
                "detail": {"layouts": sorted(layouts), "count": family.count},
            })

    if matrix is not None:
        issues.extend(_near_identical_split_issues(families, matrix, by_id))

    issues.sort(key=lambda i: (0 if i["severity"] == "alta" else 1, i["family_id"]))
    return issues


def _near_identical_split_issues(
    families: list[DocumentFamily],
    matrix: SimilarityMatrix,
    by_id: dict[str, DocumentFamily],
) -> list[dict[str, Any]]:
    """Fingerprints casi idénticos que quedaron en familias distintas."""
    doc_family: dict[str, str] = {}
    for family in families:
        for d in family.documents:
            doc_family[d.id] = family.id

    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for doc_id, nbrs in matrix.neighbors.items():
        fam_id = doc_family.get(doc_id)
        if fam_id is None:
            continue
        for other, sim in nbrs:
            if sim < NEAR_IDENTICAL_SIMILARITY:
                continue
            other_fam = doc_family.get(other)
            if other_fam is None or other_fam == fam_id:
                continue
            key = tuple(sorted((doc_id, other)))
            if key in seen:
                continue
            seen.add(key)
            issues.append({
                "kind": "near_identical_split",
                "severity": "alta",
                "family_id": fam_id,
                "other_family_id": other_fam,
                "message": (
                    f"Documentos casi idénticos ({sim:.0f}%) separados en "
                    f"familias distintas: {doc_id} ↔ {other}."
                ),
                "detail": {
                    "doc_id": doc_id, "other_id": other,
                    "similarity": sim,
                    "family_id": fam_id, "other_family_id": other_fam,
                },
            })

    return issues


# ---------------------------------------------------------------------------
# Recomendación de extractores
# ---------------------------------------------------------------------------

def recommend_extractors(
    families: list[DocumentFamily],
    coverage: CoverageResult,
    min_count: int = QUALITY_MIN_COUNT,
    top_ns: tuple[int, ...] = (5, 10, 20, 30),
) -> list[dict[str, Any]]:
    """Familias que justifican un extractor especializado.

    Criterio: volumen ≥ min_count, layout coherente (≠ DESCONOCIDO),
    extractor actual genérico (STANDARD_PARSER/UNKNOWN) y similitud alta.
    """
    total = max(coverage.total_documents, 1)
    pct_por_familia = {f.id: round(f.count / total * 100.0, 2) for f in families}

    candidatos: list[DocumentFamily] = []
    for family in sorted(families, key=lambda f: (-f.count, f.id)):
        if family.count < min_count:
            continue
        if family.dominant_layout == "DESCONOCIDO":
            continue
        if family.avg_similarity < QUALITY_MIN_SIMILARITY:
            continue
        candidatos.append(family)

    recommendations: list[dict[str, Any]] = []
    for family in candidatos[: max(top_ns)]:
        reasons = [
            f"{family.count} documento(s) ({pct_por_familia[family.id]}% del dataset)",
            f"layout coherente {family.dominant_layout}",
            f"similitud interna {family.avg_similarity:.0f}%",
            f"códigos {family.dominant_code_pattern}",
        ]
        if family.top_company:
            reasons.append(f"principal: {family.top_company}")
        recommendations.append({
            "family_id": family.id,
            "family_name": _family_display_name(family),
            "top_company": family.top_company,
            "count": family.count,
            "pct_dataset": pct_por_familia[family.id],
            "layout": family.dominant_layout,
            "code_pattern": family.dominant_code_pattern,
            "document_type": family.dominant_document_type,
            "avg_similarity": family.avg_similarity,
            "extractor_type": _extractor_type_suggestion(family),
            "reason": ". ".join(reasons) + ".",
        })

    return recommendations


def _extractor_type_suggestion(family: DocumentFamily) -> str:
    """Tipo de extractor sugerido según la estructura dominante."""
    if family.dominant_layout in ("VERTICAL", "HORIZONTAL"):
        return "SPECIALIZED_TABLE_PARSER"
    if family.dominant_layout == "LIBRE":
        return "SPECIALIZED_FREEFORM_PARSER"
    return "SPECIALIZED_PARSER"


def _family_display_name(family: DocumentFamily) -> str:
    if family.top_company:
        return f"Familia {family.top_company}"
    return f"Familia {family.dominant_layout} · {family.dominant_code_pattern}"


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def run_mining_analysis(
    records: list[DocumentRecord],
    threshold: float = 70.0,
    top_neighbors: int = 5,
    similarity_fn: Optional[Any] = None,
) -> dict[str, Any]:
    """Ejecuta el análisis completo de minería documental.

    Devuelve un dict JSON-serializable con familias, representantes,
    cobertura, calidad y recomendaciones.
    """
    t0 = time.perf_counter()

    matrix = build_similarity_matrix(
        records, top_k=top_neighbors, similarity_fn=similarity_fn,
    )
    families = detect_families(
        records, threshold=threshold, similarity_fn=similarity_fn,
    )
    representatives = select_representatives(
        families, similarity_fn=similarity_fn,
    )
    coverage = coverage_by_top_families(families)
    issues = detect_quality_issues(families, matrix)
    recommendations = recommend_extractors(families, coverage)

    stats = _dataset_statistics(records, families)

    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
        "threshold": threshold,
        "top_neighbors": top_neighbors,
        "n_documents": len(records),
        "n_families": len(families),
        "matrix": {
            "pairs_computed": matrix.pairs_computed,
            "mean_similarity": matrix.mean_similarity,
            "top_k": matrix.top_k,
        },
        "similarity_summary": matrix.to_summary_rows(),
        "families": [f.to_dict() for f in families],
        "representatives": [r.to_dict() for r in representatives],
        "coverage": coverage.to_dict(),
        "quality_issues": issues,
        "recommendations": recommendations,
        "statistics": stats,
    }
    return result


def _dataset_statistics(
    records: list[DocumentRecord],
    families: list[DocumentFamily],
) -> dict[str, Any]:
    """Distribuciones globales (empresas, layouts, patrones, extractores)."""
    companies = Counter(r.company for r in records if r.company)
    layouts = Counter(r.fingerprint.layout for r in records)
    codes = Counter(r.fingerprint.code_pattern for r in records)
    numerics = Counter(r.fingerprint.numeric_pattern for r in records)
    extractors = Counter(r.extractor for r in records)
    doc_types = Counter(r.document_type for r in records)

    variants: list[dict[str, Any]] = []
    for family in families:
        seen: set[str] = set()
        for d in family.documents:
            if d.company and d.company not in seen:
                seen.add(d.company)
                variants.append({
                    "family_id": family.id,
                    "company": d.company,
                    "layout": family.dominant_layout,
                })
    variant_counter = Counter(
        (v["company"], v["layout"]) for v in variants
    )
    top_variants = [
        {"company": c, "layout": l, "count": n}
        for (c, l), n in variant_counter.most_common(15)
    ]

    return {
        "top_companies": [
            {"name": n, "count": c} for n, c in companies.most_common(15)
        ],
        "layout_distribution": dict(layouts),
        "code_pattern_distribution": dict(codes),
        "numeric_pattern_distribution": dict(numerics),
        "extractor_distribution": dict(extractors),
        "document_type_distribution": dict(doc_types),
        "top_variants": top_variants,
    }


# ---------------------------------------------------------------------------
# Dashboard markdown
# ---------------------------------------------------------------------------

def write_dashboard_report(result: dict[str, Any], report_path) -> None:
    """Genera reports/document_mining_report.md."""
    lines: list[str] = []

    lines.append("# Data Mining del Document Knowledge Base — Report")
    lines.append("")
    lines.append(f"Generado: {result['generated_at']} "
                 f"(duración {result['elapsed_seconds']}s)")
    lines.append(f"Fingerprint-only: similitud SIN empresa ni nombre de archivo.")
    lines.append(f"Umbral de agrupación: {result['threshold']} · "
                 f"Vecinos por documento: {result['top_neighbors']}")
    lines.append("")

    # ── Resumen ejecutivo ─────────────────────────────────────────────
    lines.append("## Resumen Ejecutivo")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---|---|")
    lines.append(f"| Documentos analizados | {result['n_documents']} |")
    lines.append(f"| Familias detectadas | {result['n_families']} |")
    lines.append(f"| Pares comparados | {result['matrix']['pairs_computed']:,} |")
    lines.append(f"| Similitud media global | {result['matrix']['mean_similarity']}% |")
    lines.append(f"| Representantes | {len(result['representatives'])} |")
    lines.append(f"| Problemas detectados | {len(result['quality_issues'])} |")
    lines.append(f"| Familias candidatas a extractor | {len(result['recommendations'])} |")
    lines.append("")

    # ── Distribución ───────────────────────────────────────────────────
    lines.append("## Distribución")
    lines.append("")
    stats = result["statistics"]
    lines.append("### Layouts")
    lines.append("| Layout | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["layout_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")
    lines.append("### Patrones de códigos")
    lines.append("| Patrón | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["code_pattern_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")
    lines.append("### Patrones numéricos")
    lines.append("| Patrón | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["numeric_pattern_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")
    lines.append("### Extractores actuales")
    lines.append("| Extractor | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["extractor_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")
    lines.append("### Tipos de documento")
    lines.append("| Tipo | Documentos |")
    lines.append("|---|---|")
    for name, count in sorted(stats["document_type_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines.append("")

    # ── Top familias ───────────────────────────────────────────────────
    lines.append("## Top Familias")
    lines.append("")
    lines.append("| # | Familia | Empresa principal | Documentos | Sim. interna | "
                 "Layout | Código | Tipo doc |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, f in enumerate(result["families"][:20], start=1):
        lines.append(
            f"| {i} | `{f['id']}` | {f['top_company'] or '—'} | {f['count']} | "
            f"{f['avg_similarity']}% | {f['dominant_layout']} | "
            f"{f['dominant_code_pattern']} | {f['dominant_document_type']} |"
        )
    lines.append("")

    # ── Top empresas ───────────────────────────────────────────────────
    lines.append("## Top Empresas")
    lines.append("")
    lines.append("| Empresa | Documentos |")
    lines.append("|---|---|")
    for item in stats["top_companies"]:
        lines.append(f"| {item['name']} | {item['count']} |")
    lines.append("")

    # ── Top variantes ──────────────────────────────────────────────────
    lines.append("## Top Variantes (empresa · layout)")
    lines.append("")
    lines.append("| Empresa | Layout | Familias |")
    lines.append("|---|---|---|")
    for v in stats["top_variants"]:
        lines.append(f"| {v['company']} | {v['layout']} | {v['count']} |")
    lines.append("")

    # ── Cobertura ──────────────────────────────────────────────────────
    lines.append("## Cobertura Esperada")
    lines.append("")
    lines.append("| Top N | Familias | Documentos | % acumulado | % restante |")
    lines.append("|---|---|---|---|---|")
    for tier in result["coverage"]["tiers"]:
        lines.append(
            f"| {tier['top_n']} | {tier['families']} | {tier['documents']} | "
            f"{tier['cumulative_pct']}% | {tier['remaining_pct']}% |"
        )
    lines.append("")

    # ── Representantes ─────────────────────────────────────────────────
    lines.append("## Representantes por Familia")
    lines.append("")
    lines.append("| Familia | Documento representante | Sim. promedio | N | Empresa |")
    lines.append("|---|---|---|---|---|")
    for r in result["representatives"][:30]:
        lines.append(
            f"| `{r['family_id']}` | `{r['file']}` | {r['avg_similarity']}% | "
            f"{r['n_documents']} | {r['company']} |"
        )
    lines.append("")

    # ── Familias candidatas ────────────────────────────────────────────
    lines.append("## Familias Candidatas (extractor especializado)")
    lines.append("")
    if result["recommendations"]:
        lines.append("| Familia | Empresa | Docs | % | Layout | Código | Extractor sugerido |")
        lines.append("|---|---|---|---|---|---|---|")
        for rec in result["recommendations"]:
            lines.append(
                f"| {rec['family_name']} | {rec['top_company'] or '—'} | "
                f"{rec['count']} | {rec['pct_dataset']}% | {rec['layout']} | "
                f"{rec['code_pattern']} | {rec['extractor_type']} |"
            )
        lines.append("")
        lines.append("**Próximo extractor recomendado:** "
                     f"{result['recommendations'][0]['family_name']} "
                     f"({result['recommendations'][0]['count']} documentos, "
                     f"{result['recommendations'][0]['pct_dataset']}% del dataset) → "
                     f"{result['recommendations'][0]['extractor_type']}.")
    else:
        lines.append("Ninguna familia supera los umbrales de volumen/coherencia.")
    lines.append("")

    # ── Problemas detectados ───────────────────────────────────────────
    lines.append("## Problemas Detectados (Quality Analyzer)")
    lines.append("")
    if result["quality_issues"]:
        lines.append("| Severidad | Tipo | Mensaje |")
        lines.append("|---|---|---|")
        for issue in result["quality_issues"]:
            lines.append(f"| {issue['severity']} | {issue['kind']} | {issue['message']} |")
    else:
        lines.append("Sin problemas detectados.")
    lines.append("")

    lines.append("## Recomendación Automática")
    lines.append("")
    if result["recommendations"]:
        top = result["recommendations"][0]
        lines.append(
            f"**Desarrollar primero un `{top['extractor_type']}` para la familia "
            f"`{top['family_id']}` ({top['family_name']}).**"
        )
        lines.append("")
        lines.append(f"Justificación: {top['reason']}")
    else:
        lines.append("Aún no hay familias con volumen suficiente.")
    lines.append("")

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CSVs (compatibles con Excel: UTF-8 con BOM)
# ---------------------------------------------------------------------------

def write_csvs(result: dict[str, Any], out_dir) -> dict[str, Path]:
    """Genera families.csv, coverage.csv, clusters.csv, representatives.csv
    y similarity_summary.csv en reports/."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    families_path = out / "families.csv"
    with families_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "family_id", "name", "top_company", "documents", "avg_similarity",
            "confidence", "layout", "code_pattern", "numeric_pattern",
            "document_type", "columns", "variants",
        ])
        writer.writeheader()
        for f in result["families"]:
            writer.writerow({
                "family_id": f["id"],
                "name": _family_display_name(_family_from_dict(f)),
                "top_company": f.get("top_company", ""),
                "documents": f["count"],
                "avg_similarity": f["avg_similarity"],
                "confidence": f["confidence"],
                "layout": f["dominant_layout"],
                "code_pattern": f["dominant_code_pattern"],
                "numeric_pattern": f["dominant_numeric_pattern"],
                "document_type": f["dominant_document_type"],
                "columns": " / ".join(f["dominant_columns"]),
                "variants": len(f["companies"]),
            })

    coverage_path = out / "coverage.csv"
    with coverage_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "top_n", "families", "documents", "cumulative_pct",
            "remaining_documents", "remaining_pct",
        ])
        writer.writeheader()
        for tier in result["coverage"]["tiers"]:
            writer.writerow({
                "top_n": tier["top_n"],
                "families": tier["families"],
                "documents": tier["documents"],
                "cumulative_pct": tier["cumulative_pct"],
                "remaining_documents": tier["remaining_documents"],
                "remaining_pct": tier["remaining_pct"],
            })

    clusters_path = out / "clusters.csv"
    with clusters_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "cluster_id", "members", "avg_similarity", "confidence",
            "centroid_layout", "centroid_code_pattern", "centroid_document_type",
            "column_count",
        ])
        writer.writeheader()
        for f in result["families"]:
            centroid = f.get("centroid") or {}
            writer.writerow({
                "cluster_id": f["id"],
                "members": f["count"],
                "avg_similarity": f["avg_similarity"],
                "confidence": f["confidence"],
                "centroid_layout": centroid.get("layout", ""),
                "centroid_code_pattern": centroid.get("code_pattern", ""),
                "centroid_document_type": centroid.get("document_type", ""),
                "column_count": centroid.get("column_count", 0),
            })

    reps_path = out / "representatives.csv"
    with reps_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "family_id", "document_id", "file", "avg_similarity",
            "n_documents", "company",
        ])
        writer.writeheader()
        for r in result["representatives"]:
            writer.writerow(r)

    sim_path = out / "similarity_summary.csv"
    with sim_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "doc_id", "file", "company", "n_neighbors",
            "top1_neighbor", "top1_similarity", "mean_similarity_topk",
            "pairs_computed",
        ])
        writer.writeheader()
        for row in result["similarity_summary"]:
            writer.writerow(row)

    return {
        "families": families_path,
        "coverage": coverage_path,
        "clusters": clusters_path,
        "representatives": reps_path,
        "similarity_summary": sim_path,
    }


def _family_from_dict(f: dict[str, Any]) -> DocumentFamily:
    return DocumentFamily.from_dict(f)


# ---------------------------------------------------------------------------
# Persistencia del resultado completo (para la UI)
# ---------------------------------------------------------------------------

def save_analysis_result(result: dict[str, Any], out_path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def load_analysis_result(path) -> Optional[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
