# Technical Debt Report

Generated: 2026-07-09 16:55:20 UTC

| Problema | Impacto | Prioridad | Recomendación | Fase Sugerida |
|---|---|---|---|---|
| 82.3% de cuentas son UNKNOWN (8,780 de 10,672) | Alto — más de la mitad de las cuentas no se clasifican | CRITICAL | Priorizar enriquecimiento de variantes CMCC para Top 10 conceptos con mayor ROI | FASE 21B — Variant Enrichment |
| Layout 'validacion' tiene 4,034 UNKNOWN vs 1,335 clasificados | Medio — el layout afecta la capacidad de clasificación | MEDIUM | Analizar si el parser necesita ajustes para este layout | FASE 22 — Parser Optimization |
| Layout 'edge_cases' tiene 4,746 UNKNOWN vs 557 clasificados | Medio — el layout afecta la capacidad de clasificación | MEDIUM | Analizar si el parser necesita ajustes para este layout | FASE 22 — Parser Optimization |
| 592 cuentas tienen clasificación Shadow no incorporada oficialmente | Medio — ~5.5% de cuentas podrían reclasificarse | HIGH | Revisar y promover clasificaciones Shadow con score >= 0.90 | FASE 21B — Variant Enrichment |

*No corrections were applied. This is a diagnostic-only report.*