# Parser Quality Report — Resumen Ejecutivo

**Fecha:** 2026-08-06 10:27
**Documentos analizados:** 608 (errores: 14)
**Documentos vía OCR:** 251

## Métricas globales de extracción

| Métrica | Valor |
|---|---|
| Cuentas extraídas | 158251 |
| Cuentas con código | 14134 (8.9%) |
| Cuentas con monto | 67602 (42.7%) |
| Hallazgos de calidad totales | 24819 |

## Hallazgos por tipo

| Problema | Conteo |
|---|---|
| Símbolos residuales | 16542 |
| Totales mal interpretados | 3578 |
| Código perdido | 2755 |
| Header ghosts | 1381 |
| Montos partidos | 546 |
| Cuentas fusionadas | 12 |
| Formato de código mal detectado | 5 |

## Distribución por grupo de dataset

| Grupo | Docs | Cuentas | Hallazgos |
|---|---|---|---|
| 8_COLUMNS | 175 | 13655 | 2080 |
| ARCHIVE | 20 | 2692 | 490 |
| HOLDOUT | 137 | 17276 | 2727 |
| PROCESSING | 34 | 3022 | 520 |
| REJECTED | 3 | 0 | 0 |
| TRAINING | 76 | 93331 | 14720 |
| edge_cases | 78 | 10983 | 2745 |
| test | 1 | 138 | 13 |
| validacion | 84 | 17154 | 1524 |
