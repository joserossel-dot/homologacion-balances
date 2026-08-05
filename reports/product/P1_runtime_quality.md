# P1.2 — Auditoría de Calidad del Knowledge Runtime (SOLO LECTURA)

Fecha: 2026-08-03 · Tipo: SOLO LECTURA — ningún archivo, DB ni código modificado · Base: P1.1 (`gold_standard_runtime.db` aún no poblado; pool auditado = `gold_records`, 348 registros) · Benchmark referencia: 2660/2662 (99.92%).

---

## 0. Alcance y método

Esta auditoría evalúa la **calidad del conocimiento acumulado** que la infraestructura de promoción de P1.1
(`gold_standard/promotion.py`) llevaría al runtime. Como `gold_standard_runtime.db` todavía no existe (P1.1
entregó infraestructura sin poblar), el pool de conocimiento auditado es la tabla **`gold_records`** de
`gold_standard.db` (348 registros), que es exactamente la fuente que alimenta la promoción.

- **No se modificó** ningún archivo, DB ni código. Solo lectura (`sqlite3` + `rapidfuzz` + normalizadores del repo).
- No se ejecutó el benchmark. La estimación de impacto (F6) es analítica sobre `baseline_results.json`.
- Normalización usada: `learning.exact_match.normalize_name` (la misma que usa el motor en `engine.py:72`).

---

## 1. FASE 1 — Análisis completo del pool

| Métrica | Valor |
|---|---|
| Registros en `gold_records` | **348** |
| Con `final_code` corregido (candidatos a promover) | 348 (100%) |
| Nombres normalizados únicos | **267** |
| Registros duplicados (mismo `normalized`) | **81** |
| `normalized` con ≥2 códigos distintos | 6 |
| Códigos con ≥2 nombres distintos | múltiples (ver F2) |

### 1.1 Frecuencia de nombres normalizados (top)

| `normalized` | Frecuencia |
|---|---|
| honorarios por pagar | 4 |
| iva credito fiscal | 4 |
| disponible | 4 |
| documentos y cuentas por pagar empresas relacionadas | 4 |
| gastos de viaje y representacion | 4 |
| fondos por rendir | 3 |
| p p m por pagar | 3 |
| impuesto unico trabajadores | 3 |
| cuentas por cobrar | 3 |
| muebles y utiles | 3 |
| derechos de agua | 3 |
| iva debito fiscal | 3 |

### 1.2 Distribución de frecuencia

| Frecuencia por `normalized` | # nombres |
|---|---|
| 1 aparición | (mayoría) |
| 2 | — |
| 3 | — |
| ≥4 | — |

> La cola no está limpia: 81 registros duplicados representan el mismo concepto con variaciones de
> casing/tildes (p.ej. `Anticipo a Proveedores` vs `ANTICIPO A PROVEEDORES`). El índice único
> `(normalized, codigo_estandar)` del runtime absorberá estos duplicados de forma segura.

### 1.3 Nombres con múltiples códigos (semilla de conflictos)

| `normalized` | Códigos asignados |
|---|---|
| anticipo a proveedores | AC.01, AC.07 |
| prestamos al personal | AC.01, PC.06 |
| iva credito fiscal | AC.07, AC.08 |
| revalorizacion capital propio | PAT.01, PAT.02 |
| documentos en garantia | AC.03, AC.08 |
| anticipos de proveedores | AC.04, AC.07 |

---

## 2. FASE 2 — Conflictos

### 2.1 Ranking de conflictos (mismo `normalized` → códigos distintos)

Ordenados por nº de códigos y frecuencia:

| # | `normalized` | Nombres | Códigos | Frec. | Revisores |
|---|---|---|---|---|---|
| 1 | anticipo a proveedores | ANTICIPO A PROVEEDORES, Anticipo a Proveedores | AC.01, AC.07 | 2 | seed_script |
| 2 | prestamos al personal | PRESTAMOS AL PERSONAL, Préstamos al Personal | AC.01, PC.06 | 2 | seed_script, **analista** |
| 3 | iva credito fiscal | 4 variantes | AC.07, AC.08 | 4 | seed_script, **analista** |
| 4 | revalorizacion capital propio | 2 variantes | PAT.01, PAT.02 | 2 | seed_script, **analista** |
| 5 | documentos en garantia | 2 variantes | AC.03, AC.08 | 2 | seed_script, **analista** |
| 6 | anticipos de proveedores | Anticipos de proveedores | AC.04, AC.07 | 2 | **analista** |

**Observación clave:** los conflictos #2–#5 son **exactamente los 4 conflictos reportados en P1.1**
(`Documentos en Garantía`, `Préstamos al Personal`, `Iva Crédito Fiscal`, `Revalorización Capital Propio`)
entre el feedback del **analista** y el gold del **seed_script**. La promoción los omite (regla de
conflicto), pero deberán resolverse manualmente antes de activar el learning loop. `anticipo a proveedores`
y `anticipos de proveedores` son conflictos adicionales detectados en la frecuencia interna.

### 2.2 Mismo código → nombres muy distintos (potencial error de agrupación)

Pares dentro de un mismo código con similitud léxica < 40% (los más dispares):

| Código | Nombre A | Nombre B | Similitud |
|---|---|---|---|
| AC.07 | dividendos | p p m | 0.0 |
| AC.01 | caja | disponible | 0.0 |
| PC.06 | afp | retencion prestamo solidario | 6.5 |
| PC.02 | bcl | linea de credito santander | 6.9 |
| PC.06 | afp | mutual de seguridad cchc | 7.4 |

> Estos pares suelen ser **legítimos** (conceptos distintos que comparten código contable, p.ej. todas las
> cuentas bancarias en AC.01), pero indican que un mismo código agrupa conceptos heterogéneos — relevante
> para la calidad del gold, no un defecto del runtime.

---

## 3. FASE 3 — Sinónimos

### 3.1 Sinónimos exactos (misma normalización, distinto texto original)

Detectados **50 grupos** donde variantes de casing/tilde colapsan al mismo `normalized`, p.ej.:

- `anticipo a proveedores` ← ANTICIPO A PROVEEDORES, Anticipo a Proveedores
- `correccion monetaria` ← CORRECCION MONETARIA, Correccion Monetaria, Corrección monetaria
- `cuentas por cobrar` ← CUENTAS POR COBRAR, Cuentas Por Cobrar, Cuentas por Cobrar
- `banco santander` ← BANCO SANTANDER, Banco Santander

### 3.2 Sinónimos aproximados (similitud ≥ 70%, mismo código)

Detectados **91 pares**. Los más relevantes (mayor similitud y código común):

| Término A | Término B | Similitud | Código común |
|---|---|---|---|
| linea de credito banco chile | linea de credito bango chile | 96.4 | PC.02 |
| diferencia de cambio me | diferencia de cambio mn | 95.7 | ER.15 |
| anticipo a proveedores | anticipo proveedores | 95.2 | AC.07 |
| i v a credito fiscal | iva credito fiscal | 94.7 | AC.07 |
| cuenta corriente | cuentas corrientes | 94.1 | AC.01 |
| banco santander | banco santarder | 93.3 | AC.01 |
| p p m por pagar | ppm por pagar | 92.9 | PC.05 |
| depreciacion | depreciaciones | 92.3 | ER.07 |
| anticipo clientes | anticipo de clientes | 91.9 | PC.08 |
| anticipo a proveedores | anticipos de proveedores | 91.3 | AC.07 |

**Hallazgo de calidad:** la mayoría de los "sinónimos" aproximados son en realidad **errores de OCR /
transcripción** (`banco santarder`, `bango chile`, `lva credito fiscal`) o **variaciones de concordancia**
(singular/plural, `a`/`de`). El motor ya los absorbe vía `fuzzy_score ≥ 92`; el runtime no necesita
deduplicarlos manualmente, pero la promoción debe normalizarlos (cosa que hace `normalize_name`).

---

## 4. FASE 4 — Confianza (ALTA / MEDIA / BAJA)

Clasificación por frecuencia + consistencia (un solo código) + ausencia de conflicto.

| Nivel | Registros | % |
|---|---|---|
| **ALTA** (frec ≥2 y consistente, o confianza sugerida ≥0.9) | **213** | 61.2% |
| **MEDIA** (frec ≥1, consistente) | **121** | 34.8% |
| **BAJA** (conflicto multi-código o inconsistente) | **14** | 4.0% |

**Los 14 de BAJA son los 6 conflictos de F2** (con sus duplicados), incluyendo los 4 del analista que la
promoción ya omite. Todo el resto del pool es consistente.

---

## 5. FASE 5 — Simulación de promoción (sin escribir BD)

Aplicando las reglas de `gold_standard/promotion.py` sobre los 348 registros, contra el gold actual
(234 filas):

| Resultado | Cantidad | % |
|---|---|---|
| ✅ **Pasarían automáticamente** (clave nueva, sin conflicto) | **106** | 30.5% |
| 🔎 **Requieren revisión** (conflicto con gold) | **4** | 1.1% |
| 🗑️ **Se descartan** (palabra reservada `total`) | **11** | 3.2% |
| Duplicados absorbidos por el índice único (no aportan) | restante | — |

### 5.1 Detalle de los 4 que requieren revisión

| id | Cuenta | Código candidato | Código gold | |
|---|---|---|---|---|
| 240 | Documentos en Garantía | AC.08 | AC.03 | ⚠️ |
| 292 | Préstamos al Personal | PC.06 | AC.01 | ⚠️ |
| 296 | Iva Crédito Fiscal | AC.08 | AC.07 | ⚠️ |
| 319 | Revalorización Capital Propio | PAT.02 | PAT.01 | ⚠️ |

### 5.2 Detalle del descarte (11 con `total`)

`TOTAL GASTOS DE ADMINISTRACIÓN`, `TOTAL CAPITAL EMITIDO`, `TOTAL CUENTAS POR PAGAR...`, `TOTAL
INVENTARIOS`, `TOTAL DEUDORES COMERCIALES...` — son subtotales del balance, correctamente excluidos por la
regla de palabras reservadas.

> **Conclusión F5:** 106/348 pasan automáticamente; solo 4 requieren decisión de negocio (1.1%); 11 se
> descartan por diseño. El resto son duplicados internos que el índice único colapsa.

---

## 6. FASE 6 — Impacto esperado en el Learning Engine (estimación, sin ejecutar benchmark)

Estimación analítica sobre `baseline_results.json` (299 PDFs, **23,292 cuentas clasificadas**), comparando
qué cuentas tendrían gold match si se promovieran las 106 claves automáticas:

| Métrica | Valor |
|---|---|
| Cuentas baseline | 23,292 |
| Cuentas con gold match HOY | 2,707 (11.6%) |
| **Cuentas con gold match tras promover las 106 claves** | **≈ 3,041 (+334)** |
| — de las cuales **hoy sin clasificar** (`final_code=None`) | **101** |
| — clasificadas por otro método (dictionary/code/fuzzy) | 152 |
| Cobertura gold resultante | ≈ 13.1% (+1.5 p.p.) |

**Interpretación:**
- Las **101 cuentas hoy sin clasificar** pasarían a tener código exacto del runtime → mejora directa de
  cobertura (las 136 cuentas `unclassified` observadas en la simulación de P1.1 se reducen en ~101).
- Las **152 ya clasificadas por dictionary/code** podrían reconciliarse hacia el código runtime cuando el
  motor consulta el gold en primer lugar (`learning_exact`), pero su `final_code` final depende del orden de
  prioridad del pipeline — la estimación es un **techo** de reconciliación, no un incremento garantizado.
- **No se ejecutó el benchmark.** La cifra 2660/2662 permanece intacta y no se usa como comparación directa
  aquí porque mide otra cosa (acuerdo de clasificación, no cobertura).

---

## 7. Calidad global y recomendación final

### 7.1 Resumen

| Dimensión | Estado |
|---|---|
| Pool auditable | 348 registros, 267 conceptos únicos |
| Consistencia | **96%** del pool es consistente (ALTA+MEDIA) |
| Conflictos | 6 conceptos multi-código; 4 bloquean la promoción automática |
| Duplicados | 81 internos (absorbidos por índice único del runtime) |
| Sinónimos | 50 exactos + 91 aproximados (en su mayoría OCR/concordancia) |
| Promoción automática | 106/348 (30.5%) sin riesgo |
| Impacto estimado | +334 cuentas con gold match; +101 hoy sin clasificar |

### 7.2 Riesgos

1. **4 conflictos sin resolver** bloquean la promoción de conceptos de alta frecuencia (p.ej.
   `Iva Crédito Fiscal`, frecuencia 4). Mientras no se decidan, el runtime no los incluirá.
2. **Códigos heterogéneos** (un código con nombres muy distintos, §2.2): no es un defecto del runtime,
   pero degrada la legibilidad del gold.
3. **Sinónimos OCR** (p.ej. `santarder`) quedan en runtime como entradas separadas si superan el umbral
   fuzzy; no son dañinos pero ensucian métricas de "conceptos únicos".

### 7.3 Recomendación final

1. **Promover las 106 claves automáticas** a `gold_standard_runtime.db` (fase 1 de P1.1) — riesgo nulo,
   beneficio estimado +334 matches y +101 cuentas antes sin clasificar.
2. **Resolver manualmente los 4 conflictos** (decisión de negocio) antes de habilitar el learning loop
   completo; una vez resueltos, reintentar la promoción para incluirlos.
3. **Mantener el descarte de `total`** (11 registros) — correcto por diseño.
4. **Mantener el benchmark congelado** (`gold_standard_bench.db`, 2660/2662): nada de este proceso lo toca.
5. **Siguiente verificación**: tras poblar runtime, comparar cobertura runtime vs benchmark (shadow) antes
   de apuntar el pipeline a runtime (fase 2 de P1.1).

---

## 8. Garantías de no-modificación

- `gold_standard.db`: **no modificada** (verificada byte-idéntica al backup M1).
- `gold_standard_bench.db`, `learning/*`, `pipeline/*`, `parser/*`, `semantic/*`, `CMCC`: **no tocados**.
- No se ejecutó ninguna promoción ni escritura SQL de mutación.
- No se creó `gold_standard_runtime.db`.
- Único archivo generado: este reporte (`reports/product/P1_runtime_quality.md`).
