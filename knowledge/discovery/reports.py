from __future__ import annotations
import json
from pathlib import Path
from collections import Counter
import pandas as pd
from knowledge.discovery.cluster_engine import Cluster


def generate_reports(result: dict, output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    clusters = result['clusters']
    singletons = result['singletons']
    token_data = result['token_stats']
    ambiguous = result['ambiguous']
    total_accounts = result['total_accounts']
    clustered_accounts = result['clustered_accounts']

    # ── concept_clusters.xlsx ──
    cluster_rows = []
    for c in clusters:
        cluster_rows.append({
            'id': c.id,
            'nombre_sugerido': c.name,
            'n_variantes': c.n_members,
            'frecuencia': c.frecuencia,
            'n_empresas': c.n_empresas,
            'confianza': c.confianza,
            'miembros': ' | '.join(c.members[:20]),
        })
    cluster_df = pd.DataFrame(cluster_rows)
    cluster_df.to_excel(out / 'concept_clusters.xlsx', index=False)

    # ── concept_statistics.xlsx ──
    stat_rows = [
        {'metrica': 'Total cuentas únicas', 'valor': total_accounts},
        {'metrica': 'Cuentas agrupadas en clusters', 'valor': clustered_accounts},
        {'metrica': 'Cuentas singleton', 'valor': len(singletons)},
        {'metrica': 'Clusters formados', 'valor': len(clusters)},
        {'metrica': '% agrupado', 'valor': f'{clustered_accounts/total_accounts*100:.1f}%' if total_accounts else '0%'},
    ]
    if clusters:
        sizes = [c.n_members for c in clusters]
        stat_rows.append({'metrica': 'Cluster más grande', 'valor': max(sizes)})
        stat_rows.append({'metrica': 'Cluster más pequeño', 'valor': min(sizes)})
        stat_rows.append({'metrica': 'Promedio miembros/cluster', 'valor': round(sum(sizes)/len(sizes), 1)})
    stat_df = pd.DataFrame(stat_rows)
    stat_df.to_excel(out / 'concept_statistics.xlsx', index=False)

    # ── concept_candidates.xlsx ──
    candidate_rows = []
    for c in clusters:
        candidate_rows.append({
            'id': c.id,
            'nombre_sugerido': c.name,
            'tipo': 'cluster',
            'n_variantes': c.n_members,
            'frecuencia': c.frecuencia,
            'confianza': c.confianza,
            'accion': 'Revisar para incorporar al CMCC',
        })
    candidate_df = pd.DataFrame(candidate_rows)
    candidate_df.to_excel(out / 'concept_candidates.xlsx', index=False)

    # ── ambiguous_concepts.xlsx ──
    amb_df = pd.DataFrame(ambiguous)
    amb_df.to_excel(out / 'ambiguous_concepts.xlsx', index=False)

    # ── singleton_accounts.xlsx ──
    singletons_with_freq = []
    for s in singletons:
        singletons_with_freq.append({
            'cuenta': s,
            'frecuencia': result.get('freq_map', {}).get(s, 0) if hasattr(result, 'get') else 0,
        })
    if not singletons_with_freq:
        singletons_with_freq = [{'cuenta': s, 'frecuencia': 0} for s in singletons]
    sing_df = pd.DataFrame(singletons_with_freq)
    sing_df.to_excel(out / 'singleton_accounts.xlsx', index=False)

    # ── cluster_graph.json ──
    graph = result.get('graph', {'nodes': [], 'links': []})
    graph_path = out / 'cluster_graph.json'
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    paths = {
        'clusters': out / 'concept_clusters.xlsx',
        'statistics': out / 'concept_statistics.xlsx',
        'candidates': out / 'concept_candidates.xlsx',
        'ambiguous': out / 'ambiguous_concepts.xlsx',
        'singletons': out / 'singleton_accounts.xlsx',
        'graph': graph_path,
    }

    # ── concept_report.md ──
    top50_clusters = sorted(clusters, key=lambda c: -c.n_members)[:50]
    top50_ambiguous = ambiguous[:50]
    top50_singletons = singletons[:50]

    report = f"""# Concept Discovery Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas únicas analizadas | {total_accounts:,} |
| Clusters formados | {len(clusters)} |
| Cuentas agrupadas en clusters | {clustered_accounts:,} |
| Cuentas singleton (no agrupadas) | {len(singletons):,} |
| Porcentaje agrupado | {clustered_accounts/total_accounts*100:.1f}% |
| Pares ambiguos detectados | {len(ambiguous)} |

## 1. ¿Cuántos conceptos reales existen?

Se detectaron **{len(clusters)} clusters** que representan conceptos contables reales.
Cada cluster agrupa variantes de un mismo concepto.

## 2. ¿Cuántas cuentas quedaron agrupadas?

**{clustered_accounts:,} cuentas** ({clustered_accounts/total_accounts*100:.1f}% del total) fueron agrupadas en clusters.

## 3. ¿Cuántos singleton quedaron?

**{len(singletons):,} cuentas** quedaron como singleton (no se pudo determinar su concepto). Representan el {len(singletons)/total_accounts*100:.1f}% del total.

## 4. ¿Qué porcentaje del universo pudo agruparse?

**{clustered_accounts/total_accounts*100:.1f}%** del total de cuentas logró agruparse en clusters conceptuales.

## 5. Top 50 conceptos

| # | ID | Nombre sugerido | Variantes | Frecuencia | Confianza |
|---|-----|----------------|-----------|-----------|-----------|
"""
    for idx, c in enumerate(top50_clusters, 1):
        report += f"| {idx} | {c.id} | {c.name[:60]} | {c.n_members} | {c.frecuencia} | {c.confianza} |\n"

    report += f"""
## 6. Top 50 ambiguos

| # | Cluster A | Cluster B | Similitud | 
|---|-----------|-----------|-----------|
"""
    for idx, a in enumerate(top50_ambiguous, 1):
        report += f"| {idx} | {a['nombre_a'][:50]} | {a['nombre_b'][:50]} | {a['similitud']} |\n"

    report += f"""
## 7. Top 50 cuentas aisladas (singleton)

| # | Cuenta |
|---|--------|
"""
    for idx, s in enumerate(top50_singletons, 1):
        report += f"| {idx} | {s[:80]} |\n"

    report += f"""
## 8. Distribución de clusters

| Tamaño | Cantidad |
|--------|----------|
"""
    size_dist = Counter()
    for c in clusters:
        if c.n_members >= 50:
            size_dist['50+'] = size_dist.get('50+', 0) + 1
        elif c.n_members >= 20:
            size_dist['20-49'] = size_dist.get('20-49', 0) + 1
        elif c.n_members >= 10:
            size_dist['10-19'] = size_dist.get('10-19', 0) + 1
        elif c.n_members >= 5:
            size_dist['5-9'] = size_dist.get('5-9', 0) + 1
        else:
            size_dist['2-4'] = size_dist.get('2-4', 0) + 1
    for label in ['50+', '20-49', '10-19', '5-9', '2-4']:
        report += f"| {label} | {size_dist.get(label, 0)} |\n"

    report += f"""
## 9. Estadísticas de tokens

| Métrica | Valor |
|---------|-------|
| Tokens únicos | {token_data['unique_tokens']:,} |
| Total tokens | {token_data['total_tokens']:,} |
| Promedio tokens por nombre | {token_data['avg_tokens_per_name']} |
| Largo promedio del nombre | {token_data['avg_name_length']} |

Top tokens:
"""
    for t, c in token_data.get('top_tokens', [])[:15]:
        report += f"- \"{t}\": {c} ocurrencias\n"

    report += f"""
## 10. Recomendaciones

1. Los {len(clusters)} clusters identificados son candidatos para incorporar al CMCC.
2. Los {len(singletons)} singleton requieren revisión manual o umbral de similitud más bajo.
3. Los {len(ambiguous)} pares ambiguos deben priorizarse para desambiguación.
4. El grafo de conceptos en `cluster_graph.json` permite visualizar las relaciones.
"""
    (out / 'concept_report.md').write_text(report, encoding='utf-8')

    return paths
