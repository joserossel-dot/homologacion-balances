# Benchmark: Decision Engine V2 vs Pipeline Actual

**Date:** 2026-07-22  

**Accounts:** 11690  

**Pipeline:** Phase 1 (code -> dict -> regex) [default flags]  

**DecisionEngineV2:** DecisionEngineV2 (GS + code + dict + SM + regex, weighted ensemble)  


---

## FASE 4 — Métricas Globales

| Métrica | Pipeline Actual | DecisionEngineV2 |
|---|---|---|
| UNKNOWN | 10537 (90.14%) | 5392 (46.12%) |
| Reducción UNKNOWN | — | 5145 (48.83%) |
| Precisión estimada | 50.91% | 58.11% |
| Recall estimado | 5.02% | 31.31% |

| Métrica | Valor |
|---|---|
| Consenso promedio | 0.72 |
| Auto-decisiones | 26.9% |
| Revisiones humanas requeridas | 73.1% |
| Score promedio | 0.7058 |
| Score min/max | 0.216 / 1.0 |
| Tiempo total | 190.81s |

### Distribución de Confianza

- **VERY_HIGH**: 1966 (16.8%)
- **HIGH**: 926 (7.9%)
- **MEDIUM**: 253 (2.2%)
- **LOW**: 1353 (11.6%)
- **UNKNOWN**: 7192 (61.5%)

### Distribución de Conflictos

- **bajo**: 845 (7.2%)
- **medio**: 3 (0.0%)
- **ninguno**: 10842 (92.7%)

---

## FASE 5 — Clasificación de Diferencias

| Categoría | Cuentas | % |
|---|---|---|
| Ambos correctos | 456 | 3.90% |
| Pipeline correcto | 131 | 1.12% |
| Decision Engine V2 correcto | 3204 | 27.41% |
| Ambos incorrectos | 411 | 3.52% |
| Necesita revisión humana | 2113 | 18.08% |
| Error de Parser | 0 | 0.00% |
| Error de OCR | 0 | 0.00% |
| Error de Catálogo | 0 | 0.00% |
| Error de Regex | 0 | 0.00% |
| Error Semántico | 0 | 0.00% |
| Error de Código | 0 | 0.00% |
| Ambos UNKNOWN | 5375 | 45.98% |

---

## FASE 6 — Análisis Cuantitativo

**Mejora vs Pipeline:** +3204 cuentas (27.41%)  
**Empeora vs Pipeline:** 131 cuentas (1.12%)  
**Sin cambios:** 6242 cuentas (53.4%)  
**Ambos incorrectos:** 411  
**Necesita revisión humana:** 2113 (18.08%)  

### Contribución por Clasificador

| Clasificador | Decisiones finales | % |
|---|---|---|
| regex | 2838 | 24.3% |
| sm_tier_6 | 1310 | 11.2% |
| sm_tier_1_2 | 1022 | 8.7% |
| sm_tier_4 | 959 | 8.2% |
| dict_exact | 812 | 6.9% |
| gs_exact | 613 | 5.2% |
| dict_fuzzy | 317 | 2.7% |
| sm_tier_5 | 273 | 2.3% |
| code | 179 | 1.5% |
| gs_fuzzy | 124 | 1.1% |

### Clasificadores con menor contribución

- gs_exact: 613 decisiones
- dict_fuzzy: 317 decisiones
- sm_tier_5: 273 decisiones
- code: 179 decisiones
- gs_fuzzy: 124 decisiones

### Uso de Reglas

| Regla | Veces | % |
|---|---|---|
| R1 | 1022 | 8.7% |
| R10 | 4 | 0.0% |
| R11-R12 | 5392 | 46.1% |
| R2 | 1438 | 12.3% |
| R3-R8 | 486 | 4.2% |
| R9 | 3348 | 28.6% |

### Falsos Positivos por Threshold

| Threshold | ≥ Threshold | Estimados incorrectos | Error rate |
|---|---|---|---|
| ge_0.5 | 4498 | 2320 | 51.58% |
| ge_0.6 | 4498 | 2320 | 51.58% |
| ge_0.7 | 3145 | 967 | 30.75% |
| ge_0.8 | 2950 | 783 | 26.54% |
| ge_0.85 | 2892 | 742 | 25.66% |
| ge_0.9 | 2648 | 667 | 25.19% |
| ge_0.95 | 1966 | 372 | 18.92% |

**Threshold óptimo:** 0.5  

---

## FASE 7 — Matriz de Decisiones por Clasificador

| Clasificador | Consultado | Ganador | Descartado | Contradicho | Score Promedio | Win Rate |
|---|---|---|---|---|---|---|
| code | 313 | 182 | 11377 | 131 | 0.9385 | 58.15% |
| dict_exact | 1354 | 1084 | 10336 | 270 | 0.98 | 80.06% |
| dict_fuzzy | 393 | 328 | 11297 | 65 | 0.8403 | 83.46% |
| sm_tier_1 | 754 | 754 | 10936 | 0 | 1.0 | 100.0% |
| sm_tier_2 | 268 | 268 | 11422 | 0 | 0.95 | 100.0% |
| sm_tier_4 | 1131 | 959 | 10559 | 172 | 0.6579 | 84.79% |
| sm_tier_5 | 350 | 273 | 11340 | 77 | 0.649 | 78.0% |
| sm_tier_6 | 1621 | 1310 | 10069 | 311 | 0.6 | 80.81% |
| regex | 3375 | 3121 | 8315 | 254 | 0.8928 | 92.47% |
| gs_exact | 1130 | 842 | 10560 | 288 | 0.98 | 74.51% |
| gs_fuzzy | 176 | 125 | 11514 | 51 | 0.8308 | 71.02% |

---

## Conclusión

**GO / NO GO:** Evaluar según métricas arriba.
