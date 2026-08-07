# PARSER BASELINE — PQ-0

Baseline oficial del Parser Quality Program. Estado inicial del proyecto.

| Campo | Valor |
|---|---|
| Fecha | 2026-08-06 10:27:52 |
| Commit SHA | `dca065578f805286f1cb40a7567d8b45791e0ae7` |
| Cantidad de PDFs | 608 |
| Total de hallazgos | 24819 |

## Distribución Pareto

| Problema | Conteo | % | Acumulado % |
|---|---|---|---|
| SIMBOLO_RESIDUAL | 16542 | 66.7% | 66.7% |
| TOTAL_MAL_INTERPRETADO | 3578 | 14.4% | 81.1% |
| CODIGO_PERDIDO | 2755 | 11.1% | 92.2% |
| HEADER_GHOST | 1381 | 5.6% | 97.7% |
| MONTO_PARTIDO | 546 | 2.2% | 99.9% |
| CUENTA_FUSIONADA | 12 | 0.0% | 100.0% |
| FORMATO_MAL_DETECTADO | 5 | 0.0% | 100.0% |

## Cobertura acumulada

- Código: 8.9% | Monto: 42.7% | Combinada: 25.8%

## Tiempos

- Promedio: 28.9s | Mediana: 12.1s | Total: 17177.5s

## Benchmark congelado

| Archivo | SHA256 |
|---|---|
| `dataset_manifest.csv` | `2d383d22d7496c2e…` |
| `benchmark_results.csv` | `b5162f33cd81626c…` |
| `benchmark_summary.md` | `2bf1a11eb7a65665…` |

## Versiones

- Parser: no semver (identificado por commit SHA)
- Runtime: gold_standard/runtime_manager.py RUNTIME_SCHEMA_VERSION=1.0
- Learning: no semver (identificado por commit SHA)
- Paquete: carpeta-tributaria 0.1.0 (pyproject.toml)

> Estos archivos son inmutables. NO deben volver a modificarse.
