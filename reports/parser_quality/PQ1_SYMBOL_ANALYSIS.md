# PQ-1 · Especificación estadística de SIMBOLO_RESIDUAL

> **Sprint PQ-1.1 — Caracterización completa (solo análisis, sin implementar).**
> Fuente exclusiva: **baseline PQ-0 congelado** (`reports/parser_quality/baselines/PQ0/`,
> commit `dca065578f80…`). No se modificó ni se generará código de parser, extractores,
> Runtime, Learning, Benchmark ni tests. Este documento es la **base de especificación** para
> implementar posteriormente un limpiador conservador del nombre.
>
> Método reproducible: clasificador por patrones regex priorizados (guion `reports/parser_quality/baselines/PQ0/PQ0_findings.csv`
> + `PQ0_dataset.csv`); cada hallazgo se asigna a **un único** patrón (primera coincidencia, orden
> determinista). Todos los conteos suman exactamente **16.542** (ver §9 verificación).

---

## 0. Resumen ejecutivo

- SIMBOLO_RESIDUAL representa **16.542 / 24.819 = 66,7 %** de todos los hallazgos del PQ-0.
- Clasificados en **21 patrones mutuamente excluyentes** y agrupados en 4 decisiones:
  **LIMPIABLE 2.761 (16,7 %) · CONSERVAR 5.527 (33,4 %) · OCR 5.281 (31,9 %) · DUDOSO 2.973 (18,0 %)**.
- **El "máximo alcanzable sin riesgo" limpiando únicamente el nombre es ≈ 16–17 %**
  (≈ 2.700–2.800 de los 16.542). Un objetivo tipo **−80 % es matemáticamente imposible**
  con la restricción "solo limpiar el nombre": el **33 %** son nombres legítimos que **no deben
  tocarse** y el **32 %** es ruido irrecuperable (fuentes `(cid:)`, OCR basura).
- 6 patrones son directamente limpiables de forma segura (ver §5). 11 patrones NO deben tocarse
  (ver §6). 3 patrones son dudosos y requieren reglas conservadoras o revisión (ver §7).

---

## 1. Metodología

1. **Extracción**: todas las filas `tipo == SIMBOLO_RESIDUAL` de `PQ0_findings.csv` → 16.542.
2. **Join**: `PQ0_dataset.csv` por `archivo` para `ocr_o_texto` (origen OCR/nativo) y `grupo`.
3. **Pre-filtro de ruido** (`head`), en orden:
   - `(cid:` → `GR_CID_font` (fuente sin ToUnicode).
   - nombres de ≥ 12 caracteres con < 45 % de letras → `GR_basura_ocr` (líneas OCR con alta
     densidad de dígitos/símbolos; ver §9.2 para el límite).
4. **Clasificación estructural** (nombres legibles): 15 regex priorizados (primera coincidencia
   gana). El sub-patrón de paréntesis de cierre (`PARCIERRA`) se subclasifica en 4 variantes por
   balanceo y semántica; el `&` se subclasifica por adyacencia de letras.
5. **Decisión** de cada patrón: LIMPIABLE / CONSERVAR / OCR / DUDOSO (basada en ejemplos reales
   extraídos y en el riesgo de alterar semántica).
6. **Escenarios de reducción** (§7): suma de patrones LIMPIABLE = "sin riesgo".

**Límites del método** (ver §9): el campo `nombre` en el CSV está truncado a 80 caracteres; el
detector original operó sobre el nombre completo. ~1891 hallazgos (antes de esta clasificación)
podrían tener el símbolo en la parte truncada; aquí se reclasificaron por el fragmento visible
(mínimo impacto: son una fracción minoritaria y mayoritariamente ruido).

---

## 2. Tabla maestra de patrones

Ordenados por frecuencia (n | % | % acumulado | PDFs | OCR | con-código). Regex mostrada
abreviada; detalles en §5.

| # | Patrón (id) | Detección (regex sobre `nombre`) | n | % | acum % | PDFs | OCR | c/código | Decisión |
|----|--------------|----------------------------------|-----:|-----:|-----:|-----:|-----:|-----:|----------|
| 1 | `PT_equilibrada` | termina en `)` con paréntesis balanceado | 3.042 | 18,39 | 18,39 | 224 | 551 | 206 | **CONSERVAR** |
| 2 | `GR_CID_font` | contiene `(cid:` | 2.697 | 16,30 | 34,69 | 5 | 0 | 0 | **OCR** |
| 3 | `GR_basura_ocr` | ≥12 chars y <45 % letras | 1.873 | 11,32 | 46,01 | 124 | 323 | 245 | **OCR** |
| 4 | `CURRENCY` | contiene `US$`, `U$S`, `CH$`, `CL$`, `CLP`, `USD` | 1.598 | 9,66 | 55,67 | 80 | 180 | 103 | **CONSERVAR** |
| 5 | `PCT_NUM` | `\d[\d.,]*%` (% pegado a cifra) | 1.503 | 9,09 | 64,76 | 129 | 236 | 874 | **DUDOSO** |
| 6 | `RESTO` | ningún patrón anterior | 1.252 | 7,57 | 72,33 | 101 | 111 | 326 | **DUDOSO** |
| 7 | `S$FINAL` | `\s\$\s*$` ($ suelto al final) | 994 | 6,01 | 78,34 | 61 | 102 | 33 | **LIMPIABLE** |
| 8 | `ATG` | contiene `@` | 711 | 4,30 | 82,64 | 14 | 0 | 0 | **OCR** |
| 9 | `S$SUELTO_I` | `(?<=\s)\$(?=\s)` ($ token suelto interior) | 608 | 3,68 | 86,31 | 69 | 64 | 11 | **LIMPIABLE** |
| 10 | `PT_stray` | termina en `)` desbalanceado | 543 | 3,28 | 89,59 | 85 | 122 | 8 | **LIMPIABLE** |
| 11 | `PCT_OTRO` | `%` sin pegar a cifra | 543 | 3,28 | 92,87 | 63 | 89 | 1 | **CONSERVAR** |
| 12 | `PARABR` | termina en `(` | 489 | 2,96 | 95,83 | 50 | 24 | 3 | **LIMPIABLE** |
| 13 | `PT_cneto` | termina en `(neto|menos|bruto…)` | 220 | 1,33 | 97,16 | 33 | 51 | 2 | **CONSERVAR** |
| 14 | `S$PEG_NUM` | `$` pegado a cifra interior | 218 | 1,32 | 98,48 | 39 | 51 | 1 | **DUDOSO** |
| 15 | `S$INI` | `^\$` ($ suelto inicial) | 69 | 0,42 | 98,90 | 12 | 8 | 0 | **LIMPIABLE** |
| 16 | `S$INI_NUM` | `^\$\d` ($ + cifra inicial) | 57 | 0,34 | 99,24 | 15 | 10 | 0 | **LIMPIABLE** |
| 17 | `PT_num` | termina en `)` tras dígito (totales) | 40 | 0,24 | 99,48 | 24 | 16 | 1 | **CONSERVAR** |
| 18 | `HASHH` | contiene `#` | 31 | 0,19 | 99,67 | 3 | 0 | 6 | **CONSERVAR** |
| 19 | `AMP_pair_legit` | `letra&letra` (G&A, A&P, B&C) | 27 | 0,16 | 99,83 | 10 | 0 | 10 | **CONSERVAR** |
| 20 | `AMP_stray` | `&` no adyacente a letras | 26 | 0,16 | 99,99 | 11 | 0 | 0 | **DUDOSO** |
| 21 | `DASHFIN` | termina en `-{1,}` | 1 | 0,01 | 100,00 | 1 | 0 | 0 | **LIMPIABLE** |
| | **TOTAL** | | **16.542** | 100 | 100 | 320 | 1.938 | 1.136 | |

**Lectura rápida:** el **33 %** del problema es nombres correctos que el detector marca por su
patrón (falsos positivos → CONSERVAR). El **32 %** es ruido no recuperable (OCR). Solo el
**16,7 %** es limpiable sin riesgo.

---

## 3. Decisiones — resumen por categoría

| Decisión | Patrones | n | % | Comentario |
|----------|----------|-----:|-----:|------------|
| **LIMPIABLE** | S$FINAL, S$SUELTO_I, S$INI, S$INI_NUM, PARABR, PT_stray, DASHFIN | **2.761** | **16,69** | Símbolo inequívocamente residual; quitar no altera el nombre |
| **CONSERVAR** | PT_equilibrada, CURRENCY, PCT_OTRO, PT_cneto, PT_num, HASHH, AMP_pair_legit, AMP_stray | **5.527** | **33,41** | Legítimos; el detector los marca por falso positivo |
| **OCR** | GR_CID_font, GR_basura_ocr, ATG | **5.281** | **31,92** | Irrecuperable desde el texto; requiere otra vía (ToUnicode/OCR/fuente) |
| **DUDOSO** | PCT_NUM, RESTO, S$PEG_NUM | **2.973** | **17,97** | Mezcla legítimo/residual; requiere reglas finas o revisión manual |
| | | **16.542** | 100 | |

---

## 4. Ejemplos reales por patrón (extraídos del baseline)

| Patrón | Ejemplos (nombre) |
|--------|--------------------|
| `S$FINAL` | `Capital $` · `Otros Activos Reservas $` · `Ventas nacionales $` · `Total Ingresos de la explotación $` |
| `S$SUELTO_I` | `Activos Corrientes $ Pasivos Corrientes` · `Cuenta — Descripción Debe $ Haber $ Saldo…` · `SANTIAGO $ TNORPENDENCIA BALANCE. GENERAL,` |
| `S$INI` | `$ Costo de Ventas` · `$ Desde Enero Hasta Diciembre de` · `$ - 0UF` |
| `S$INI_NUM` | `$83.090, por los pagos provisionales mensuales (PPM) cancelados a…` · `$ 0 $` |
| `PARABR` | `TOTAL PARTICIPACIONES EN LAS GANANCIAS (` · `_ (` · `[1102012] Banco Scotiabank (` |
| `PT_stray` | `Departamento de Comrpbiliqo)` · `jIrqueo)` · `l f,)` |
| `DASHFIN` | `marcaEbaramodeloDWO/E300de2,2kw,…` (garbage aislado) |
| `PT_equilibrada` | `Obligaciones con el público (pagarés)` · `…-porción corto plazo (bonos)` · `Mat. Prepar. Vitrinas (Visual)` |
| `CURRENCY` | `DEPOSITO A PLAZO EN US$` · `INCOMES USD %/SALE USD %/SALE` · `US$ US$` |
| `PT_cneto` | `Valores negociables (neto)` · `Deudores por venta (neto)` · `Documentos por cobrar (neto)` |
| `PT_num` | `70+71+72)` · `TOTAL A PAGAR (Lineas 68+69)` |
| `PCT_OTRO` | `Margen Explotación / Ingresos Explotac. (%) 22.45 %` · `Gastos de Adm. y Vtas / Ingresos Explot. (%) 10.05 %` |
| `PCT_NUM` | `Impuesto Unico Art, 21(35%)` · `…Reajuste Art. 72 línea 68: 0.6%` · `Resultado Explotación / Ingresos Explotac. (%) 8.32 % 16.71%` |
| `HASHH` | `PINTOR GUSTAVO CABELLO OLGUIN #` · `AVDA LA DIVISA #0340 COMUNA SAN BERNARDO…` |
| `AMP_pair_legit` | `40161GASTOS MARKETING A&P` · `Sergio Contreras Vega B&C Consultores Ltda` |
| `AMP_stray` | `Javiera Sagrista, Ansieta & Pizarro Auditores Asociados Ltda` · `úá & o OÓÓ` |
| `GR_basura_ocr` | `| REMUNERACIONESPOR — 856.159.690 970.6050%4` · `FREIGHT REVENUES ORCA YAGAN 6.335.323 41,3% 5.839.120 40,0%` |
| `GR_CID_font` | `(cid:1)(cid:2)(cid:3)…` · `%(cid:29)(cid:4)&(cid:8)…` |
| `ATG` | `AO@UNÓN@ U ortrP` · `oó++NNO+O@lJ@J@!@óOO@OÓA@Q@…` |

---

## 5. Reglas de limpieza concretas (patrones LIMPIABLE)

Regla general: **funcionar solo sobre el `string nombre` ya construido** (`parsear_linea`,
post-línea `547`), nunca sobre `tokens`/`codigo`/`monto`. Aplicar en orden, conservando primero
las protecciones de §6. Cada regla es un regex de detección + acción de sustitución. **Sin tocar
el detector ni el benchmark.**

| Regla | Detecta (regex) | Acción | Casos | Seguridad |
|-------|------------------|--------|------:|-----------|
| **R1 · `$` suelto final** | `\s\$\s*$` | reemplazar por `` (quitar `$` + espacios sobrantes) | 994 | Símbolo sin texto al final; nunca cambia significado |
| **R2 · `$` suelto interior** | `(?<=\s)\$(?=\s)` | quitar el token `$` (dejar un espacio colapsado) | 608 | `$` entre palabras claramente no es parte del nombre |
| **R3 · `$` inicial** | `^\$` | quitar el `$` inicial (permite recuperar código en `S$INI_NUM`) | 126 | No altera el texto restante |
| **R4 · `(` final sin cierre** | `\(\s*$` | quitar el `(` final | 489 | Truncamiento; nada que perder |
| **R5 · `)` desbalanceado final** | `\)\s*$` (y cuenta de `(`=0 ó sin par) | quitar el `)` sobrante | 543 | Solo si no hay `(` de apertura |
| **R6 · guiones finales** | `-{1,}\s*$` | quitar | 1 | Ídem |

> Todas las reglas se aplican **después** de las protecciones de §6 (nunca antes).
> Resultado esperado del set completo: **2.761 hallazgos eliminados del detector** (=16,69 %).

---

## 6. Patrones que NO deben tocarse (CONSERVAR)

El limpiador debe ser **no-op** (devolver el nombre intacto) para estos casos. Son nombres
**correctos** que el patrón `_RESIDUAL_IN_NOMBRE` marca por falso positivo:

| Patrón | Por qué no tocar | Ejemplo |
|--------|------------------|---------|
| `PT_equilibrada` | Paréntesis balanceado es parte legítima del nombre | `Obligaciones con el público (pagarés)` |
| `CURRENCY` | Divisa real del estado (`US$`, `CH$`, `CLP`, `USD`, `M$`) | `DEPOSITO A PLAZO EN US$` |
| `PT_cneto` | Sufijo normativo `(neto)/(menos)/(bruto)` | `Deudores por venta (neto)` |
| `PT_num` | Totales numéricos / referencias `(Línea 68+69)` | `70+71+72)` |
| `PCT_OTRO` | Ratios/porcentajes del texto (`%` en `Margen… (%)`) | `Margen Explotación / Ingresos Explotac. (%)` |
| `HASHH` | `#` de direcciones y numeraciones (`#0340`) | `AVDA LA DIVISA #0340 …` |
| `AMP_pair_legit` | `&` en nombres (`A&P`, `B&C`) | `Sergio Contreras Vega B&C Consultores Ltda` |
| `AMP_stray` | `&` en personas/jurídicas | `Ansieta & Pizarro Auditores Asociados Ltda` |

**Regla de protección global:** si el nombre contiene **cualquier** token `US$`, `U$S`, `CH$`,
`CL$`, `CLP`, `USD`, `M$` **o** termina en `)` con paréntesis balanceado **o** contiene `&` entre
letras → no limpiar (salvo la regla R1/R2 que solo actúa sobre `$` *suelto*, nunca sobre `US$`
— ver §7.1 sobre tokenización).

---

## 7. Patrones DUDOSOS — cómo tratarlos (sin implementar)

| Patrón | Riesgo | Regla conservadora propuesta |
|--------|--------|------------------------------|
| `PCT_NUM` (1.503) | `%` puede ser legítimo: `21(35%)` (impuesto), ratios | NO borrar `%` del texto. **Solo** si el token `NN,N%` es el **último token** del nombre y es claramente un monto residual (regla: `\d[\d.,]*%$`), descartarlo. Estimación prudente: < 10 % de este grupo. |
| `RESTO` (1.252) | Mezcla: headers (`M$ ANTERIOR M$`), guiones de nombres, `$` en cabeceras | No limpiar globalmente. Revisar solo los que terminan en guión o `$` tras espacios (caerían en R1/R6). El resto: dejar. |
| `S$PEG_NUM` (218) | `$` pegado a cifra, a menudo dentro de OCR ruidoso | Solo si `$` pegado está en **posición final de token de monto** y sin texto detrás; caso contrario dejar. |
| `AMP_stray` (26) | Mayormente `&` OCR suelto, pero hay nombres legítimos | No tocar `&` nunca (bajo beneficio, alto riesgo). |

**Regla adicional (tokenización segura):** toda limpieza de `$` debe operar sobre el **token**
completo. `US$`/`CH$`/`M$` (2–3 caracteres con letras pegadas al `$`) se conservan; solo el `$`
aislado (token `$` solo, o `$` pegada a dígitos en posición residual final) se elimina. Esto
garantiza que nunca se degrade `US$`.

---

## 8. Estimación del máximo de reducción alcanzable sin riesgo

Base: **16.542** hallazgos SIMBOLO_RESIDUAL (66,7 % del total de 24.819 del PQ-0).

### Escenario A — Sin riesgo (recomendado)
Suma de patrones **LIMPIABLE** (reglas R1–R6):

```
994 (S$FINAL) + 608 (S$SUELTO_I) + 69 (S$INI) + 57 (S$INI_NUM)
+ 489 (PARABR) + 543 (PT_stray) + 1 (DASHFIN) = 2.761
```

**≈ 2.761 → 16,7 % de SIMBOLO_RESIDUAL** (= 11,1 % de los hallazgos totales).
Tras aplicar: SIMBOLO_RESIDUAL pasa de 16.542 → ~13.781; hallazgos totales ~24.819 → ~22.058.

### Escenario B — Moderado (con reglas finas de §7, aún conservador)
Añade una fracción prudente de `PCT_NUM` (token `%` final, ≈ 5–10 % del grupo) y algunos
`S$PEG_NUM`/`RESTO` en posición final de monto.

**Estimación: ≈ 3.200–3.500 → 19–21 %.** Se requiere validación por muestreo antes de aceptar.

### Escenario C — Agresivo (NO recomendado)
Todo DUDOSO: 16,7 + 18,0 ≈ **34,7 %**. Implica borrar `%`/`$`/`&` del texto y mutilar nombres
legítimos → **rechazado** por riesgo de degradación de fidelidad.

### Conclusión de reducción

> **El máximo alcanzable sin riesgo es ≈ 16–17 % (≈ 2.700–2.800). Con reglas finas y muestreo
> de validación, se puede aspirar a ≈ 19–21 %. La meta de −80 % del análisis estratégico es
> inalcanzable con la restricción "solo limpiar el nombre"**, porque el 33 % del contador son
> falsos positivos legítimos y el 32 % es ruido irrecuperable.

**Por qué no más:** el limpiador solo puede actuar sobre símbolos que NO forman parte del nombre.
`(bonos)`, `(neto)`, `US$`, `A&P`, `#0340`, `35%` son contenido válido; el detector los seguirá
marcando tras la limpieza (son falsos positivos del patrón, no errores de extracción).

---

## 9. Riesgos, límites y verificación del método

### 9.1 Riesgos de la futura implementación
1. **CRÍTICO — tocar `US$`/`(bonos)`/`(neto)`/`A&P`**: mitigado con protección de §6 (no-op).
2. **ALTO — "gaming" del contador** (borrar `(cid:)` para que no marque): prohibido; esos 2.697
   no se cuentan como reducción honesta.
3. **MEDIO — `$` interior en cabeceras de doble columna** (`Activos $ Pasivos`): R2 los fusiona;
   aceptable porque el `$` no es parte del nombre.
4. **BAJO — interacción con `es_total`/clasificación**: la limpieza es post-nombre; no altera
   `codigo`, `monto` ni `origen_columna`.

### 9.2 Límites del análisis
- `nombre` truncado a 80 chars en el CSV. La clasificación se hizo sobre el fragmento visible.
  Impacto estimado: ~11 % de hallazgos podrían tener el símbolo más allá del corte
  (mayoritariamente ruido); el patrón de detector real se aplica sobre el nombre completo, por lo
  que los conteos de reducción son **cota inferior** (un limpiador que actúa sobre el nombre
  completo podría eliminar algunos más).
- `GR_basura_ocr` (umbral <45 % letras) agrupa tanto OCR-basura puro como algunos estados
  multi-columna con columnas `%` (p. ej. `FREIGHT REVENUES ORCA … 41,3%`). Es un bucket
  intencionalmente amplio y **excluido** de la reducción sin riesgo.

### 9.3 Verificación de la consistencia
- Suma de patrones = **16.542** (100 %). Suma de decisiones = LIMPIABLE 2.761 + CONSERVAR 5.527
  + OCR 5.281 + DUDOSO 2.973 = **16.542**.
- OCR total del dataset (1.938 casos) concentrado en `GR_basura_ocr` (323), `PT_equilibrada`
  (551, falso positivo), `PCT_NUM` (236), `CURRENCY` (180) → el símbolo no es un problema
  exclusivo de OCR: **el 88 % viene de texto nativo**.
- Los 2.697 de `(cid:)` viven en **solo 5 PDFs** (p. ej. `BALANCE CLASIFICADO CENTRAL 2019`,
  `Notas Explicativas Central 2019`) → resolución futura es de pipeline/ToUnicode, no de
  limpiador.

---

## 10. Recomendación para el futuro limpiador (spec, sin implementar)

1. **Alcance**: función pura `limpiar_nombre_cuenta(nombre: str) -> str`, aplicada únicamente al
   `nombre` en `parsear_linea()` (post-línea 547). Sin efectos en código/montos/clasificación.
2. **Contrato mínimo**: aplica R1–R6 (§5) respetando protecciones (§6); **no-op** ante
   CURRENCY/paréntesis balanceado/`&`-letras/`%`-palabra.
3. **Determinismo**: loop de punto fijo (máx. 3 pasadas), espacios colapsados, sin crear nombres
   < 4 caracteres (si tras limpiar queda vacío → devolver el original).
4. **Verificación**: suite con ≥ 25 ejemplos reales del baseline (20 limpables + 15 protegidos) +
   re-ejecución de la auditoría y `compare`/`gate` contra PQ-0.
5. **Objetivo aceptable (realista)**: **SIMBOLO_RESIDUAL −16 % (incondicional)** con *stretch*
   de −19/−21 % sujeto a muestreo. NO perseguir −80 %.
