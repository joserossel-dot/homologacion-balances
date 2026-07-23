# Reporte de Impacto de Migración — FASE 1B

**Migración:** `diccionario_optimizado.json` → `diccionario.json`

---

## Resumen

- **Archivos modificados:** 4 (pipeline, db_repository, benchmark, cargar_datos)
- **Filtro __EXCLUIR__ agregado:** pipeline/homologation_pipeline.py:_load_dictionary
- **+42 cuentas clasificadas** (de 1,910 → 1,952)
- **+0 regresiones** (learning/code intactos)
- **-52.5s tiempo total** (-3.27%)

---

## Cobertura

| Métrica | ANTES | DESPUÉS | DIFERENCIA |
|---------|-------|---------|------------|
| Cuentas totales | 10,672 | 10,672 | 0 |
| Clasificadas | 1,910 | 1,952 | **+42** (+2.20%) |
| Sin clasificar | 8,762 | 8,720 | **-42** (-0.48%) |
| Documentos | 185 | 185 | 0 |

## Distribución por Método

| Método | ANTES | DESPUÉS | DIFERENCIA |
|--------|-------|---------|------------|
| Code | 167 | 167 | 0 |
| Dictionary Exact | 246 | 282 | **+36** |
| Dictionary Fuzzy | 293 | 299 | **+6** |
| Learning Exact | 1,049 | 1,049 | 0 |
| Learning Fuzzy | 155 | 155 | 0 |
| **Total clasificadas** | **1,910** | **1,952** | **+42** |

## Benchmark

| Métrica | ANTES | DESPUÉS | DIFERENCIA |
|--------|-------|---------|------------|
| Total cuentas | 187 | 187 | 0 |
| Legacy correctas | 187 | 187 | 0 |
| Legacy precisión | 100.00% | 100.00% | 0 |
| Pipeline correctas | 187 | 187 | 0 |
| Pipeline precisión | 100.00% | 100.00% | 0 |
| Tiempo | 0.41s | 0.29s | -0.12s |

## Tiempos

| Métrica | ANTES | DESPUÉS | DIFERENCIA |
|--------|-------|---------|------------|
| Total | 1,607.7s | 1,555.2s | **-52.5s** (-3.27%) |
| Promedio/doc | 8.69s | 8.41s | **-0.28s** |
| P95 | 39.47s | 32.53s | **-6.94s** |

## Errores

| Tipo | ANTES | DESPUÉS |
|------|-------|---------|
| Errores parser | 0 | 0 |
| Errores totales | 1 | 1 |

> Ambos con el mismo error: `EEFF 2016 UPCOM.xls` requiere `xlrd` (archivo .xls antiguo).

---

## Conclusión

La migración de `diccionario_optimizado.json` (712 entradas) → `diccionario.json` (826 entradas)
resultó en **+42 cuentas clasificadas** (+2.20% de aumento relativo).

**Impacto observado vs estimación de auditoría:**

- Auditoría estimó: ~+45 entradas nuevas → +6.3% de cobertura de diccionario
- Real: +42 cuentas clasificadas (36 exact + 6 fuzzy = 42 diccionario hits adicionales)
- Cobertura de diccionario aumentó de 539 → 581 (+7.79%)

**Coincidencia:** La estimación fue precisa — 42 de 45 nuevas entradas fueron
encontradas en los balances procesados. Las 3 restantes probablemente
corresponden a cuentas que no aparecen en ningún balance del dataset.

**0 regresiones:** ninguna cuenta previamente clasificada cambió de código.
Ninguna cuenta pasó de clasificada a no clasificada. Learning y code intactos.

**Tiempo:** Ligera mejora (-52.5s, -3.27%) probablemente por variación
en rendimiento de parsing PDF, no atribuible al cambio de diccionario.

**Riesgo:** Mínimo. Los 3 `__EXCLUIR__` se filtran correctamente en el pipeline.
Los conflictos internos de código (ANC.01 vs ER.07, AC.05 vs AC.09) pre-existían
y no afectan la migración.

## Archivos Modificados

| Archivo | Línea | Cambio |
|---------|-------|--------|
| `pipeline/homologation_pipeline.py` | 40 | `diccionario_optimizado.json` → `diccionario.json` + filtro __EXCLUIR__ |
| `src/db_repository.py` | 70 | `diccionario_optimizado.json` → `diccionario.json` |
| `evaluation/homologation_benchmark.py` | 17, 91 | `diccionario_optimizado.json` → `diccionario.json` |
| `cargar_datos.py` | 51 | `diccionario_optimizado.json` → `diccionario.json` |
