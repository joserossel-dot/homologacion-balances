# Parser Quality — Diff de auditoría

**Baseline:** `/Users/josealfonsorossel/AI-Projects/homologacion-balances/reports/parser_quality/baselines/PQ0` (608 docs)

**Current:** `/Users/josealfonsorossel/AI-Projects/homologacion-balances/reports/parser_quality` (608 docs)

**Fecha:** 2026-08-06 10:27

> Baseline inicial (sin comparación previa).


### Variación por tipo de error

| Tipo | Baseline | Current | Variación |
|---|---|---|---|
| CODIGO_PERDIDO | 2755 | 2755 | 0 |
| CUENTA_FUSIONADA | 12 | 12 | 0 |
| FORMATO_MAL_DETECTADO | 5 | 5 | 0 |
| HEADER_GHOST | 1381 | 1381 | 0 |
| MONTO_PARTIDO | 546 | 546 | 0 |
| SIMBOLO_RESIDUAL | 16542 | 16542 | 0 |
| TOTAL_MAL_INTERPRETADO | 3578 | 3578 | 0 |


### PDFs mejorados (menos hallazgos)

| Archivo | Baseline | Current |
|---|---|---|


### PDFs empeorados (más hallazgos)

| Archivo | Baseline | Current |
|---|---|---|


### Variación por PDF (solo con cambio)

| Archivo | Baseline | Current | Variación |
|---|---|---|---|


### Cobertura acumulada (Pareto) — antes

| Problema | Conteo | Acumulado |
|---|---|---|
| SIMBOLO_RESIDUAL | 16542 | 66.7% |
| TOTAL_MAL_INTERPRETADO | 3578 | 81.1% |
| CODIGO_PERDIDO | 2755 | 92.2% |
| HEADER_GHOST | 1381 | 97.7% |
| MONTO_PARTIDO | 546 | 99.9% |
| CUENTA_FUSIONADA | 12 | 100.0% |
| FORMATO_MAL_DETECTADO | 5 | 100.0% |


### Cobertura acumulada (Pareto) — después

| Problema | Conteo | Acumulado |
|---|---|---|
| SIMBOLO_RESIDUAL | 16542 | 66.7% |
| TOTAL_MAL_INTERPRETADO | 3578 | 81.1% |
| CODIGO_PERDIDO | 2755 | 92.2% |
| HEADER_GHOST | 1381 | 97.7% |
| MONTO_PARTIDO | 546 | 99.9% |
| CUENTA_FUSIONADA | 12 | 100.0% |
| FORMATO_MAL_DETECTADO | 5 | 100.0% |


### Top 10 → 95% (después)

| Problema | Conteo | % | Acumulado |
|---|---|---|---|
| SIMBOLO_RESIDUAL | 16542 | 66.7% | 66.7% |
| TOTAL_MAL_INTERPRETADO | 3578 | 14.4% | 81.1% |
| CODIGO_PERDIDO | 2755 | 11.1% | 92.2% |
| HEADER_GHOST | 1381 | 5.6% | 97.7% |


### Tiempo (s)

| Métrica | Baseline | Current |
|---|---|---|
| Promedio | 28.9 | 28.9 |
| Mediana | 12.1 | 12.1 |
| Total | 17177.5 | 17177.5 |

## Notas de cobertura

- **Baseline:** código 8.9% | monto 42.7% | combinada 25.8%
- **Current:**  código 8.9% | monto 42.7% | combinada 25.8%

