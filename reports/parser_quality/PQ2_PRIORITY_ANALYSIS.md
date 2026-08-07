# PQ-2 · Análisis de prioridad — Próximo problema con mayor ROI

> **Post-cierre de PQ-1.** PQ-1 se considera **sprint de investigación completado**: la auditoría
> demostró que solo **16,7 %** de SIMBOLO_RESIDUAL es corregible automáticamente; el 83,3 %
> restante son nombres legítimos (falsos positivos), ruido OCR irrecuperable (`(cid:)`) o casos
> dudosos. No se implementa el limpiador ni ningún otro cambio.
>
> Este análisis recalcula el **Pareto REAL** del proyecto (eliminando falsos positivos, categorías
> no accionables y ruido OCR) y prioriza el próximo problema por retorno de inversión.
>
> **Base exclusiva:** baseline **PQ-0 congelado** (`reports/parser_quality/baselines/PQ0/`),
> commit `dca065578f80…`. Métricas medididas con el clasificador determinista (cada hallazgo a un
> patrón) y las columnas `PQ0_dataset.csv`/`PQ0_findings.csv` + `benchmark/dataset_manifest.csv`.
> **No se modificó código.**

---

## 0. Punto de partida (PQ-0 oficial)

| Campo | Valor |
|---|---|
| PDFs | 608 (594 válidos + 14 corruptos) |
| Cuentas | 158.251 |
| Total hallazgos | 24.819 |
| Cobertura código | **8,93 %** (14.134 / 158.251) ← **la más débil** |
| Cobertura monto | 42,72 % |
| Benchmark congelado | 20 archivos / 1.470 hallazgos detectados |

---

## 1. Pareto REAL — qué es realmente accionable

Simplificación del Pareto bruto restando lo no accionable (falsos positivos legítimos + OCR
irrecuperable + dudoso). Los conteos "accionables" provienen de medición (grep/join sobre el
baseline), no de estimaciones.

| Categoría | Pareto bruto | % bruto | Falsos positivos / no accionables | **Accionable** | % del total | Concentración |
|---|------------|-------:|----------------------------------|-------:|-----:|---|
| SIMBOLO_RESIDUAL | 16.542 | 66,7 % | `(bonos)` 3.042, `(neto)` 220, `US$` 1.598, `%` ratios 543, `&`/`#` 84, `(cid:)` 2.697, OCR basura 1.873, `@` 711, dudoso 2.973… | **2.761** | 11,1 % | 320 PDFs |
| TOTAL_MAL_INTERPRETADO | 3.578 | 14,4 % | ~15 % sin keyword total | **≈ 3.070** | 12,4 % | 355 PDFs (CPT*) |
| CODIGO_PERDIDO | 2.755 | 11,1 % | ~0 % (código visible en raw en **100 %** de casos) | **2.755** | 11,1 % | **34 PDFs** (top-6 = 85 %) |
| HEADER_GHOST | 1.381 | 5,6 % | ~0 % (por definición son cabeceras admin) | **1.381** | 5,6 % | 260 PDFs |
| MONTO_PARTIDO | 546 | 2,2 % | mayormente OCR multi-columna | ~546 (dudoso) | 2,2 % | 41 PDFs |
| CUENTA_FUSIONADA | 12 | 0,0 % | – | 12 | 0,0 % | 8 PDFs |
| FORMATO_MAL | 5 | 0,0 % | – | 5 | 0,0 % | 3 PDFs |

**Lectura clave:** una vez eliminado el ruido y los falsos positivos, deja de haber un
"problema gigante": **TOTAL_MAL, CODIGO y SIMBOLO (real) son casi del mismo tamaño (~2.700–3.070)**.
Por eso la prioridad debe decidirse por **ROI (impacto × esfuerzo × riesgo × efecto en cobertura/
homologación)**, no por el conteo Pareto bruto. Los ~16.542 de SIMBOLO eran engañoso: 83,3 %
de ellos no se pueden corregir tocando solo el nombre.

---

## 2. Comparativa por categoría — dimensiones completas

### 2.A · CODIGO_PERDIDO — **RECOMENDADO (PQ-2)**

| Dimensión | Evaluación |
|---|---|
| **Impacto esperado** | Recuperar **2.755 códigos** (100 % accionable, código visible en `raw` en todos). Pasa la cobertura de código de **8,93 % → 10,67 %** (+1,74 pp / +19,5 % relativo). Única categoría que sube la métrica más débil. |
| **Concentración** | **34 PDFs**; top-6 (Pre Balance VFCH, ECDS, Pre Balance CASA, Capiro…) = **85 %** de casos. → alto apalancamiento por archivo y testeo acotado. |
| **Esfuerzo** | **MEDIO.** Raíz: detección de formato (falla a `SIN_CODIGO`) + splitting de línea. Requiere ajustar `PATRONES_CODIGO`/`detectar_formato_codigo` en `parsear_linea`. |
| **Riesgo** | **MEDIO‑ALTO**: toca el núcleo de parseo (área protegida). Mitigación: acotado a 34 archivos y validable por re-ejecución (el código es *ground truth*: si aparece tras el parseo, el fix funcionó). |
| **Efecto benchmark** | 189 hallazgos del tipo en los 20 archivos congelados (6,9 % del tipo). Un fix correcto **mejora** el resultado del benchmark (permite re-congelar tras aprobación). |
| **Efecto cobertura** | **ALTO**: sube cobertura de código (la más crítica). |
| **Efecto homologación** | **ALTO**: el código es la clave universal para homologar cuentas entre empresas; sin él el cruce es a nombre. |
| **Efecto Learning Loop** | **ALTO**: varias features del loop dependen del código; recuperar código mejora el etiquetado y minería. |
| **Efecto Runtime** | NULO (el Runtime no interviene en el parseo). |
| **Prioridad** | **1 (máxima ROI)** |

---

### 2.B · TOTAL_MAL_INTERPRETADO — segundo lugar

| Dimensión | Evaluación |
|---|---|
| **Impacto esperado** | ~3.070 casos (85,8 % matchean keyword `TOTAL/SUMAS/SUBTOTAL/RESULTADO`). Corrige doble contabilidad: filas de total tratadas como cuentas y `es_total` mal etiquetado. |
| **Concentración** | 355 PDFs (amplio, poco en cada uno); familia `CPT*` (Gonzagri, Folatre, Exportadora, Saldarriaga) concentra los picos (194/156/156/154). |
| **Esfuerzo** | **MEDIO**: refinar la lógica de detección de totales existente (`PATRON_TOTAL`/`es_total`), validando no sobre-etiquetar. |
| **Riesgo** | **MEDIO**: cambiar `es_total` altera la clasificación; si se sobre-marca, se degrada la extracción de sus cuentas. |
| **Efecto benchmark** | 225 hallazgos en el benchmark (6,3 % del tipo) → mejorable. |
| **Efecto cobertura** | Neutro‑positivo (los totales no son cuentas reales; corregirlos diseña filas limpias). |
| **Efecto homologación** | **ALTO**: limpia filas de total y evita que filas de total se cuelen como cuentas. |
| **Efecto Learning Loop** | Mediano. |
| **Efecto Runtime** | NULO. |
| **Prioridad** | **2** |

---

### 2.C · HEADER_GHOST — quick win de bajo riesgo

| Dimensión | Evaluación |
|---|---|
| **Impacto esperado** | **1.381** líneas extraídas como cuentas (Giro, RUT, fechas `AL 31 DE DICIEMBRE DE 2024`, `Balance Clasificado`, `PATRIMONIO`…). Removerlas higieniza la tabla de cuentas. |
| **Concentración** | 260 PDFs, promedio ~5,3 por archivo; tope `EEFF Arg San Osvaldo` (75). |
| **Esfuerzo** | **BAJO**: ampliar/afinar `GARBAGE_PATTERNS` + `_ADMIN_HEADER` (cabeceras administrativas, títulos, fechas). |
| **Riesgo** | **BAJO**: solo descarta líneas sin código y con patrón administrativo; no afecta a las cuentas reales. |
| **Efecto benchmark** | 84 hallazgos (pequeño). |
| **Efecto cobertura** | Levemente positivo: quitar 1.381 filas sin código → código ~9,0 % (+ ~0,1 pp). |
| **Efecto homologación** | Bajo‑medio (no aporta códigos ni montos; solo higiene). |
| **Efecto Learning Loop** | Bajo. |
| **Efecto Runtime** | NULO. |
| **Prioridad** | **3 (opción de quick‑win barato)** |

---

### 2.D · SIMBOLO_RESIDUAL_REAL (16,7 %)

| Dimensión | Evaluación |
|---|---|
| **Impacto esperado** | Solo 2.761 (16,7 % de su bruto). Bajo costo: cosmetización de nombres. |
| **Concentración** | 320 PDFs (muy disperso). |
| **Esfuerzo** | **BAJO** (limpiador puro de string). |
| **Riesgo** | **BAJO** (solo nombre; protección de `US$`/`(neto)`/`(bonos)`). |
| **Efecto benchmark** | 312 detectables (5,7 % del tipo). |
| **Efecto cobertura** | NULO (no afecta código ni monto). |
| **Efecto homologación** | Bajo‑medio (nombres más limpios pero la clave sigue siendo el código). |
| **Efecto Learning Loop** | Bajo. |
| **Efecto Runtime** | NULO. |
| **Prioridad** | **4 (despriorizado)** — fácil pero con retorno estratégico bajo; no justifica su propio sprint como objetivo único. |

---

## 3. Modelo de scoring (transparente, pesos explícitos)

Pesos orientados al objetivo del proyecto (homologación de balance):

| Dimensión (peso) | CODIGO | TOTAL_MAL | HEADER | SIMBOLO_Real |
|---|---|---|---|---|
| Impacto a tamaño (0,20) | 3 | 4 | 2 | 3 |
| Cobertura código (0,25) | **5** | 3 | 3 | 1 |
| Efecto homologación (0,20) | 5 | 4 | 2 | 2 |
| Esfuerzo inverso (0,15) | 3 | 2 | 5 | 4 |
| Riesgo inverso (0,05) | 3 | 2 | 5 | 5 |
| Learning Loop (0,10) | 5 | 3 | 2 | 1 |
| Benchmark inverso (0,05) | 4 | 4 | 5 | 4 |
| **Ponderado** | **4,15** | **3,20** | **3,90** | **2,40** |

> `CODIGO` gana por la combinación única: sube la métrica más débil (cobertura de código),
> impacto máx. en homologación y Learning, y todo el mercado es de bajo riesgo acotado a 34 PDFs.
> `HEADER` queda segundo en score por ser quick-win de bajo riegro (aunque menor impacto).

---

## 4. Recomendación final

### **PQ-2 = CODIGO_PERDIDO (Recuperación de códigos perdidos)**

- **100 % accionable y medible** (2.755; el código está en `raw` en el 100 % de casos → ground
  truth verificable).
- **Concentrado**: 34 PDFs, top-10 = 85 %. Alta apalancamiento por unidad de esfuerzo.
- **Único que actúa sobre la métrica de cobertura de código (8,93 % → 10,67 %)**, la más
  correlacionada con la homologación.
- **Máximo efecto** en homologación y en el Learning Loop (features por código).
- Riesgo **MEDIO‑ALTO** (toca el núcleo del parseo) pero acotado y verificable por re-conteo.

**Quick-win opcional** (si se quiere un sprint corto de acompañamiento): HEADER_REMOTE con
esfuerzo/riesgo bajos (1.381 limpias).

---

## 5. Criterios de aceptación sugeridos para PQ-2 (sketch, sin implementar)

(Cuantitativos, medidos sobre benchmark PO-0.)

1. **Coherencia**: código visible en `raw` → código presente en `codigo` (meta: recuperar ≥ 2.000 de 2.755).
2. **Cobertura de código** ≥ 10 % (objetivo: ~10,67 %).
3. **Sin regresiones**: `n_cuentas_con_codigo` no puede diminuir en ninguna otra región; `compare` PASS y `parser_quality_gate` PASS.
4. **Benchmark**: sin empeorar el resultado de los 20 archivos congelados; si **mejora**, re-congelar **solo** tras aprobación (el `benchmark_results` mutable si se percato).
5. **Otros tipos sin regresión** (SIMBONO/TOTAL_MAL/HEADER no pueden crecer).
6. Test suite en verde + snapshot de archivos protegidos inmutable.

---

## 6. Anexo — datos medidos (apéndice)

**Benchmark exposure por tipo (baseline PQ-0):**
SIMBONO 948 · TOTAL_MAL 225 · CODIGO 189 · HEADER 84 · MONTO 18 · FUSION 3 · FORMATO 3.

**Accionabilidad medida:**
- CODIGO_PERIDO: 2755/2755 (100%) con código visible en `raw`.
- TOTAL_MAL: 3069/3578 (85,8 %) con keyword total.
- HEADER_GHOST: 1381/1381 por definición (no-code + `_ADMIN_HEADER`).

**Cobertura base (recomputada del `PQ0_dataset.csv`):** 158251 cuentas; código 14134 (8,93 %);
monto 67602 (42,72 %). Con CODIGO fijado +2755 → código 16889 (10,67 %).

> Archivo de referencia del mismo ciclo: `PQ1_SYMBOL_ANALYSIS.md` (caracterización completa con sus
> conteos por patrón).