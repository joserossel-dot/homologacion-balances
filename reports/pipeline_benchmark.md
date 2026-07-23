# Pipeline Benchmark Report

**Date:** 2026-07-22

---

## Global Comparison

| Metric | Legacy (MotorHibridoLocal) | New (HomologationPipeline) | Delta |
|---|---|---|---|
| Documentos procesados | 182 | 182 | — |
| Cuentas totales extraídas | 30829 | 30829 | — |
| Cuentas clasificadas (con código) | 5389 | 2816 | -2573 |
| UNKNOWN (sin código) | 8363 | 10936 | +2573 |
| Cobertura bruta | 17.48% | 9.13% | -8.35% |
| Acuerdos (mismo código) | — | — | 10209 |
| Discrepancias (código diferente) | — | — | 2880 |
| Documentos con cambios | — | — | 151 |
| | | | |
| Tiempo parseo total | — | — | 1551.2s |
| Tiempo clasificación total | 8.5s | 120.3s | +111.8s |
| Tiempo promedio por doc (parse) | — | — | 8.52s |
| Tiempo promedio por doc (clasif) | 0.05s | 0.66s | +0.61s |


## Coverage by Account Type

| Type | Legacy | New | Delta | Notes |
|---|---|---|---|---|
| ACTIVO | 2156 | 878 | -1278 | Pipeline no incluye regex fallback |
| PASIVO | 885 | 500 | -385 | Pipeline no incluye regex fallback |
| PATRIMONIO | 618 | 409 | -209 | Pipeline no incluye regex fallback |
| PERDIDA | 1700 | 1029 | -671 | Pipeline no incluye regex fallback |
| OTROS | 30 | 0 | -30 | Códigos sin prefijo estándar (ej: __EXCLUIR__) |
| UNKNOWN | 8363 | 10936 | +2573 | Cuentas sin clasificar por ningún método |

## Disagreement Patterns

| Pattern | Count | Interpretation |
|---|---|---|
| AC → NONE | 862 | Legacy clasifica como AC (vía regex) pero pipeline no |
| ER → NONE | 587 | Legacy clasifica como ER (vía regex) pero pipeline no |
| PC → NONE | 407 | Legacy clasifica como PC (vía regex) pero pipeline no |
| ANC → NONE | 396 | Legacy clasifica como ANC (vía regex) pero pipeline no |
| PAT → NONE | 241 | Legacy clasifica como PAT (vía regex) pero pipeline no |
| ER → ER | 80 | Mismo tipo (ER) pero código específico diferente |
| AC → AC | 44 | Mismo tipo (AC) pero código específico diferente |
| NONE → PC | 43 | Pipeline clasifica donde legacy no puede |
| PNC → NONE | 34 | Legacy clasifica como PNC (vía regex) pero pipeline no |
| ER → PC | 33 | Clasificaciones contradictorias entre motores |
| ER → PAT | 30 | Clasificaciones contradictorias entre motores |
| ANC → ANC | 27 | Mismo tipo (ANC) pero código específico diferente |
| __E → NONE | 21 | Legacy clasifica como __E (vía regex) pero pipeline no |
| ER → AC | 17 | Clasificaciones contradictorias entre motores |
| NONE → ANC | 8 | Pipeline clasifica donde legacy no puede |
| PC → PAT | 8 | Clasificaciones contradictorias entre motores |
| PNC → PC | 8 | Clasificaciones contradictorias entre motores |
| AC → ANC | 7 | Clasificaciones contradictorias entre motores |
| AC → PC | 6 | Clasificaciones contradictorias entre motores |
| NONE → ER | 5 | Pipeline clasifica donde legacy no puede |

---

## Analysis

### 1. ¿Dónde gana el nuevo pipeline?

- Clasifica 60 cuentas que el legacy no puede (gold standard + dictionary exact)
- Arquitectura extensible: soporta CMCC, AccountTypeFilter, LayoutDetector
- Precisión potencialmente mayor: prioriza gold standard sobre regex heurístico
- Trazabilidad completa: cada clasificación incluye method + reason documentados

### 2. ¿Dónde sigue ganando el legacy?

- Cobertura total: 5389 vs 2816 (+2573)
- Reglas regex (37 patrones): capturan 2,548 cuentas que el pipeline no clasifica
- Velocidad: 0.05s vs 0.66s por documento (13x más rápido)
- Corrección por columna: desambigua 7 pares de nombres (arriendos, intereses, etc.)
- Mayor cobertura en todos los tipos: ACTIVO, PASIVO, PATRIMONIO, PERDIDA

### 3. Gap para igualar al legacy

**Faltan 2573 cuentas (47.7%) para igualar la cobertura del legacy. El 99% de la brecha (2,548/2,573) son cuentas que el legacy captura vía regex y el pipeline no tiene.**

| Métrica | Valor |
|---|---|
| Cuentas faltantes | 2573 |
| Porcentaje del legacy | 47.7% |
| Recuperables vía regex | 2,548 (99% del gap) |
| Nuevas capturas del pipeline | 60 (no existían en legacy) |

### 4. Principal cuello de botella

**Parseo de PDF (extracción de texto + OCR) — 1,551s (92% del tiempo total)**

- Parseo PDF: 1551.2s (92% del total)
- OCR en ~50% de documentos: cada PDF escaneado requiere pdftoppm + tesseract
- Pipeline clasificación: 120.3s (7% del total)
- Legacy clasificación: 8.5s (<1% del total, solo string operations)

### 5. Cambio único de mayor impacto

**Incorporar las 37 reglas regex del legacy como fallback en HomologationPipeline — recuperaría ~2,500 cuentas (95% de la brecha). Segundo: agregar corrección por columna para pares ambiguos (arriendos, intereses, etc.).**

Impacto estimado: ~95% del gap actual (2,448/2,573 cuentas recuperables)

Implementación: Migrar REGLAS_COMPILADAS de app_validacion.py al pipeline como _classify_by_regex() — sin modificar la lógica existente.

### Resumen visual del gap

```
Legacy:  ######################## 5,389 clasificadas
New:     ############ 2,816 clasificadas
Gap:     ############ 2,573 (47.7%)

Del gap:
  ████████████████████████████████ 2,548 recuperables vía regex
  ██ 25 no identificadas
  60 nuevas capturas del pipeline
```

---
*Generated by run_pipeline_benchmark.py*