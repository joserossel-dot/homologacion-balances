# Auditoría técnica — SIMBOLO_RESIDUAL (PQ-1)

> **Sprint PQ-1 · Fase 0 — Análisis.** Documento de auditoría técnica del hallazgo
> **SIMBOLO_RESIDUAL** (16.542 de 24.819 hallazgos totales; **66,7 %** del Pareto de PQ-0).
> 100 % construido sobre los artefactos congelados de `baselines/PQ0` y sobre el código leído.
> **No se implementa nada aquí** (Fase 1). Referencia: `PQ1_STRATEGIC_ANALYSIS.md` (FASE 3).
>
> Fecha: 2026-08-06 · Commit baseline: `dca065578f80…`

---

## 0. Fuente del hallazgo (patrón del auditor)

En `reports/parser_quality/audit_parser_quality.py:66` el detector es:

```python
_RESIDUAL_IN_NOMBRE = re.compile(r'[\$%#@&]|[\-]{1,}\s*$|\(\s*$|\)\s*$|[\w][\-·]\s*$')
```

O sea, un nombre se considera residual si **contiene** `$ % # @ &` en cualquier posición, o
**termina** en `-`, `(`, `)` o `letra+[-·]`. **Conclusión crítica:** este patrón también
marca nombres **perfectamente legítimos** (p. ej. `Deudores (neto)`, `Obligaciones (bonos)`,
`Depósito en US$`). Por tanto **no todos los 16.542 son "símbolos residuales reales"**
(ver §4 falsos positivos).

---

## 1. ¿Dónde se origina el nombre? — traza del pipeline

Todos los extractores (universal, perfil/familia, doble columna) delegan el parseo a
`ParserPDF.parsear()` → **cuando de tr. `parsear_linea()`**. No existe otra ruta que
construya `CuentaRaw.nombre` (verificado: `extractors/{universal,profile_driven,double_column,specialized,factory}.py`).
Por tanto **hay un único punto de generación del nombre**.

### Punto crítico: `parsear_linea()` — `parser_universal.py:526-547`

```python
526  tokens = resto.split()
527  descartados_finales = 0
528  while tokens and descartados_finales < 2 and \
529          not re.search(r'\d', tokens[-1]) and len(tokens[-1]) <= 2:
530      tokens.pop(); descartados_finales += 1   # <-- solo elimina tokens finales cortos sin dígito

533  montos_tokens = []
534  i = len(tokens) - 1
535  while i >= 0:
536      tok_norm = normalizar_token_ocr(tokens[i])
537      if tok_norm == '-':
538          montos_tokens.insert(0, '0'); i -= 1
540      elif PATRON_MONTOS.fullmatch(tok_norm.replace('$', '')):
541          montos_tokens.insert(0, tok_norm.replace('$', ''))   # <-- solo quita '$' PREFIJO del monto
542          i -= 1
543      else:
544          break
546  nombre_tokens = tokens[:i + 1]
547  nombre = ' '.join(nombre_tokens).strip(' .-')
```

**Diagnóstico técnico del punto:** la limpieza de símbolos solo ocurre en dos micro-casos
(bucle de 528 quita tokens finales cortos sin dígito; el `replace('$','')` de 541 solo cuando el
`$` está PEGADO al token de monto). Todo símbolo que no sea "un token suelto corto al final" o
"`$` pegado al monto" **pasa intacto al `nombre`**. El nombre se construye por simple `' '`.join
de los tokens restantes, **sin ninguna normalización de caracteres residuales**.

El 49,6 % de hallazgos tiene `raw == nombre` y el patrón también matchea `raw` en ~100 % de los
casos con símbolo interior (§3.3): **el símbolo entra con la línea extraída del PDF; el parser NO
lo crea, pero tampoco lo retira al construir el nombre.** → El problema es una **brecha de
limpieza del nombre**, no una corrupción del parser.

---

## 2. Mecanismos exactos verificados

Codificado y ejecutado el `parsear_linea()` real. Resultados (entrada → salida):

| Entrada (línea del PDF)                    | código | nombre                                | Causa                                                                 |
|---------------------------------------------|--------|---------------------------------------|----------------------------------------------------------------------|
| `11010 CAJAS $ 1.234.567`                   | 11010  | `'CAJAS $'`                           | `$` motivo SUELTO entre nombre y monto: 540 solo funciona si `$` pegado. **Bucle 528 no lo alcanza (no es token final si hay monto).** |
| `11010 CAJAS $1.234.567`                    | 11010  | `'CAJAS'`                             | OK — `$` pegado se retira (540). |
| `$1105-03 IMPORTACIONES 391.689.139`        | **None**| `'$1105-03 IMPORTACIONES'`           | `$` inicial rompe `PATRONES_CODIGO_LINEA` → **código perdido** y `$` entra al nombre. |
| `EBITDA 7.938.892 51,8%`                    | None   | `'EBITDA 7.938.892 51,8%'`           | `PATRON_MONTOS` no admite `%` → el monto con `%` no se quita y **`51,8%` entra al nombre**. |
| `EBITDA 7.938.892 51,8 %`                   | None   | `'EBITDA'`                           | `%` suelto final sí lo descarta el bucle 528. |
| `… GANANCIAS (`                              | None   | termina en `(`                       | Nadie retira un `(` final. |
| `… 12.007.476 12.007.476 )` → `)` en medio | —      | termina en `)`                       | `)` fuera de posición final (antes del monto) no lo alcanza ni 528 ni 540. |
| `1105 Valores negociables (neto)`            | —      | `'… (neto)'`                         | Legítimo; marcado por el detector (falso positivo). |
| `1105 CAJA $` (sin monto)                    | —      | `'1105 CAJA'`                        | `$` final suelto + sin monto → bucle 528 lo retira (caso ya resuelto). |

**Resumen de mecanismos que generan SIMBOLO_RESIDUAL:**
1. `$` como token **suelto** entre nombre y monto → queda en el nombre.
2. `$` **inicial** rompe la detección de código → `$` + pérdida de código.
3. `%` **pegado a una cifra final** → entra al nombre (monto con `%` no parseable).
4. `( … ` **abierto final / `)` desbalanceado** → quedan tal cual.
5. **Símbolos del propio PDF** (`@ & # $ %) presentes en la capa de texto (OCR o nativo)
   → difunden al nombre porque no hay normalización.
6. **Fuentes `(cid:N)`** sin mapa ToUnicode → el texto extraído es literal `(cid:N)`.

---

## 3. Taxonomía empírica — 16.542 casos sobre datos reales congelados

Clasificación por forma del nombre (cada caso es mutuamente excluyente; ver §2 orden de prioridad).
Columnas: `n` casos · `%` · pdfs afectados · `OCR` (docs cuyo documento es OCR, segregado por
`ocr_o_texto`).

| # | Categoría | n | % | pdfs | OCR | Ejemplo real |
|---|-----------|-----:|----:|----:|----:|--------------|
| F | **Símbolo interior (real)** | **8.296** | **50,2 %** | 232 | 1.044 | `CAJAS $`, `EBITDA… 51,8%`, `… US$ …` |
| C2| `( … )` balanceado **legítimo** | 3.367 | 20,4 % | 231 | 624 | `Obligaciones con el público (bonos)` |
| A | **Fuente `(cid:N)` sin ToUnicode** | 2.697 | 16,3 % | **5** | 0 | `(cid:1)(cid:2)(cid:3)…` |
| G | Otro (línea OCR basura pura) | 795 | 4,8 % | 72 | 44 | `o H r > … @ o … z` (Xpovin) |
| C3 | `)` **desbalanceado** (artefacto) | 645 | 3,9 % | 104 | 176 | `ARTICULOS ASEO … )`, `70+71+72)` |
| B | **Truncado en `(` abierto** | 616 | 3,7 % | 53 | 25 | `TOTAL PARTICIPACIONES EN LAS GANANCIAS (` |
| C1 | `(neto)` legítimo | 117 | 0,7 % | 24 | 24 | `Valores negociables (neto)` |
| D | Termina en `-` | 9 | 0,1 % | 4 | 1 | `…-` |
| | **TOTAL** | **16.542** | 100 % | 320 | 1.938 | |

**OCR: solo 1.938 / 16.542 (11,7 %).** → SIMBOLO_RESIDUAL es mayoritariamente un problema de
**texto nativo** (88 %), no de OCR. (Corrige la lectura del análisis estratégico que no
discriminaba el origen.)

### 3.1 Detalle de la categoría F «símbolo interior» (8.296) — sub-buckets

| Sub-bucket | n | Origen técnico | Limpiable por normalizador |
|------------|-----|----------------|---------------------------|
| `%` (porcentaje pegado a monto final) | 2.645 | Monto con signo `%` no parseable (mecanismo §2.3) | **Sí** (si es trailing). Riesgo: columnas % legítimas |
| `$` suelto (…) | 1.837 | Mecanismo §2‑1 (`CAJAS $ …`) | **Sí** — caso estrella |
| `US$` (legítimo) | 1.439 | Divisa auténtica en nombre | **NO** tocar (falso positivo) |
| `@` | 1.320 | OCR/fuente con `@` (casi todo basura de `Xpovin`-family) | Parcial (basura irrecuperable) |
| `$ cifra` (`… $1.234`) | 1.161 | `$` pegado a cifra que no quedó como monto | **Parcial** (depende de detección de monto) |
| `#` | 105 | `… #`, `10.2023 BALANCE … #` | ✔ `#` al final |
| Empieza con `$` | 87 | Mecanismo §2‑2 (+ pérdida de código) | ✔ + recupera código |
| `&` | 72 | `G&A`, `A&P` (legítimo) o basura | No los `A&xxx` legítimos |

### 3.2 Fuente `(cid:)` — caso especial (16,3 %, 5 pdfs)
BALANCE CLASIFICADO CENTRAL 2019 y otros 4: PDF con fuentes tipo CID-keyed **sin tabla
ToUnicode**, `(pdfplumber)` devuelve `(cid:N)` literal. Estos nombres son irrecuperables con un
limpiador de nombre (la información ya no está en el texto). **Requieren pipeline/OCR** (ToUnicode
o forzado OCR). Fuera del alcance de PQ-1 (no tocar benchmark/fuentes; documentado).

### 3.3 Rastrear si el símbolo también está en `raw`
- `$`/`%`/etc. en `nombre` ⇒ **~100 % también en `raw`** → **origen = extracción del PDF**, no el parser.
- En ~50 % de los casos `raw == nombre` (sin separación código/monto).

---

## 4. Falsos positivos del detector (importantes para el objetivo)

Del patrón `\)\s*$` y `\$` se marcan nombres legítimos. Calibración real:

| Subgrupo legítimo | n | decisión |
|---|---|---|
| `(neto)` / `(bruto)` / `(bonos)` / `(pagarés)` | 3.484 | **Preservar** (no limpiar) |
| `US$` | 1.439 | Conservar |
| `G&A` / `A&P` | ~72 | Conservar |
| **Suma** | **~4.995 (≈30 %)** | — |

Estos no son "errores a corregir": son nombres correctos. El limpiador debe ser **conservador** y
NO reducir este fragmento (o se degrada la fidelidad del nombre). Ver §8.

---

## 5. Top PDFs que concentran SIMBOLO_RESIDUAL (datos congelados)

| PDF | n | Nota |
|-----|----|------|
| Notas Explicativas Central 2019.pdf | 2.414 | junto con fuentes `(cid:)` |
| ECDS Balance 10-2020 (1).pdf | 2.118 | `%`/`$` columnas mezcladas |
| Balance Xpovin.pdf | 615 | OCR/garbage `@ &` |
| Balances Grupo.pdf | 588 | `(…)` |
| David del Curto EEFF 2018 … BORRADOR.pdf | 484 | columnas % |

---

## 6. FORMA DE LA SOLUCIÓN ÚNICA — «limpiador de nombre» conservador

**Cumple 100 % las restricciones del sprint** (no toca código, montos, clasificación, benchmark):
es una **función pura de POST-PROCESO sobre el `string nombre`** ya construido. No modifica
`tokens`, ni la detección de código, ni la separación de montos, ni `OrigenColumna` ni `es_total`.

### Propuesta (`_limpiar_nombre_cuenta(nombre: str) -> str`), comportamiento:

1. **Reglas de preservación (en orden, primero):**
   - Si `nombre` termina en `)` y tiene `(` balanceados en el interior → **return sin cambios**
     (protege `(bonos)`, `(neto)`, `(pagarés)`, `(ella)`). Los paréntesis de sustantivos se mantienen.
   - Preservar apariciones de `US$`, `USD`, `CH$`, `CLP` (moneda en el nombre).
   - Preservar tokens como `G&A`, `A&P` que tienen letras en ambos lados del símbolo.
   - **Nunca** acortar el nombre a < 4 caracteres ni borrarlo; devolver al menos el texto residual.
2. **Limpieza de residuos (solo cuando no activan las preservaciones):**
   - Quitar `$` si es **token suelto** (con espacio a ambos lados) que aparece entre nombre y montos,
     o un `$` inicial al comienzo (además recupera la chance de código).
   - Quitar un `%` final o un `%` pegado a una última cifra que sea claramente un monto (`[0-9.,]%$`).
   - Eliminar un `(` abierto al final SIN par de cierre → quitarlo (repara el truncado de §B).
   - Eliminar un `)` no balanceado (sin par de apertura) → removerlo (repara §C3).
   - Quitar `$`, `#`, `@`, `&` cuando NO estén adyacentes a letras (evita tocar `G&A`).
   - Quitar guiones finales múltiples (`-{2,}`) o el patrón `letra-`/`letra·` al final.
   - Normalizar espacios múltiples → uno solo (regex `\s+`).
   - Aplicar en loop hasta punto fijo (máx. 3 pasadas).
3. **Determinísimo** y sin efecto sobre `codigo`/`monto` (func de un solo string).

---

## 7. Punto exacto de inserción

Único y verificable (todos los extractores pasan aquí):

```
parser_universal.py
  def parsear_linea(...):
     …
 546  nombre_tokens = tokens[:i + 1]
 547  nombre = ' '.join(nombre_tokens).strip(' .-')
 548  nombre = _limpiar_nombre_cuenta(nombre)          # ← INSERCIÓN
 549  if not nombre or len(nombre) < 3:               # ← guarda se mantiene (usa el nombre limpio)
 550      return None
```

**Por qué aquí y no en `parsear()` posterior:** aquí `nombre` ya es la string definitiva de la
cuenta, independiente de código/monto; es la única vía común (generic/universal/doble columna
siempre llaman `parsear_linea`); y no interfiere con el detector de formato ni con `PATRON_MONTOS`.

Alternativa considerada (post-facto en `parsear()` sobre todas las cuentas) → se descarta: el
`es_total`, `origen_columna` y la exclusión de líneas basura actúan sobre `nombre` y conviene que la
decisión se haga con el nombre ya limpio y deduplicado (menor ruido).

---

## 8. Riesgos

| Riesgo | Nivel | Mitigación |
|--------|------|------------|
| Borrar contenido legítimo (`(bonos)`, `(neto)`, `US$`, `G&A`) | **CRÍTICO** | Preservaciones de §6.1 + suite de no-regresión sobre nombres conocidos |
| Gaming del métrico (borrar `(cid:)` para que el detector no marque) | **ALTO** | No limpiar cid; documentar como irrecuperable. Prohibir «limpiar para ocultar». |
| Detector vuelve a marcar `(neto)`/`US$` (no se reducen) → el objetivo −80 % se vuelve inalcanzable | **ALTO** | Replantear la meta (ver §10) — 30 % de hallazgos son falsos positivos/legítimos |
| Alterar `es_total` / clasificación | MEDIO | Solo tocar el string; `es_total=bool(PATRON_TOTAL.match(nombre))` sigue sobre el nombre limpio (el prefijo `total` no cambia) |
| Regresión en código/montos | BAJO | Limpieza de post-proceso; nunca vuelve a tocar `tokens`/`monto` |
| Sobre-limpieza del OCR-garbage irrecuperable (mejora cosmética) | MEDIO | No perseguir `-0 %` de símbolos; aceptar el piso por cid/garbage/legítimos |

---

## 9. Estrategia de implementación (Fase 1+)

1. **Congelar snapshot protegido** del estado (hash) — ya existe `baselines/PQ0/_PQ0_hashes.json` + `/tmp/protected_before.txt`.
2. **Implementar `_limpiar_nombre_cuenta`** como función pura nueva (no editar el pipeline salvo 2 líneas: inserción + import). Sin tocar parseo aritmético.
3. **Crear el corpus `tests/test_limpiador_nombre.py`**: (a) ejemplos §2 (mecanismos), (b) al menos 30 nombres reales tomados de `PQ0_findings.csv` para cada categoría, (c) assert de **no-cambio** sobre `(bonos)`, `(neto)`, `US$`, `G&A`, y sobre la preservación de código/monto.
4. **Re-ejecución**: `reports/parser_quality/audit_parser_quality.py --resume` (checkpoints intactos) → CSVs de corriente.
5. **Comparación** `tools/parser_quality_compare.py --baseline baselines/PQ0 --current reports/parser_quality` → `parser_quality_diff.md`.
6. **Gate** `reports/parser_quality` / baselines: `parser_quality_gate.py`.
7. Si PASS → meter a `HISTORY.md` como PQ-1 (idempotente). Si FAIL → revertir.

---

## 10. Criterios de aceptación (cuantitativos y verificables)

### RECOMENDACIÓN: reajustar el objetivo del sprint

Dado que **~30 % (≈4.995 / 16.542)** de SIMBOLO_RESIDUAL son **nombres legítimos o falsos
positivos** (paréntesis de sustantivos `(bonos)`, sufijo `(neto)`, moneda `US$`, `G&A`), el techo
teórico de reducción *limpiando solo el nombre* es **≈ −70 % si además se eliminan los
`(cid:)`**, pero los cid son irrecuperables. **Techo realista y honesto: −55 %/−70 %.**

| # | Criterio | Meta |
|---|----------|------|
| 1 | Reducción de hallazgos `n_simbolo_residual` | **≥ 55 %** (≤ ~7.440) · *stretch*: ≥ 70 % |
| 2 | Sin regresión de cuentas/`codigo`/`monto` | cobertura ≥ PQ-0: código ≥ 8,9 % · monto ≥ 42,7 % |
| 3 | No nuevas regresiones en ningún `tipo` (diff no negativo en otras categorías) | compare PASS |
| 4 | Benchmark (20 archivos congelados): **sin nuevas** debajo de PQ-0; re-ejecutar y comparar | benchmark sin regresión; hash literal **puede** cambiar si una cuenta mejoró → re-congelar solo tras aprobación |
| 5 | Preservación: `(neto)`, `(bonos)`, `US$`, `G&A` quedan **intactos** en el nombre | tests: ≥ 20 asserts |
| 6 | El `-80 %` del análisis estratégico se evalúa EXPLÍCITAMENTE contra el techo (§8) y *no* como línea dura | documentado y aceptado |
| 7 | Todos los tests (`tests/test_*`) en verde (≥ 18 existentes + ≈ 20 nuevos) | PASS |
| 8 | Hash de archivos protegidos idéntico tras la re-ejecución | unchanged |

> **Nota de honestidad:** NO intentar bajar el contador a cualquier costa (p. ej. borrando
> `(bonos)` o `(cid:)`). Eso inflaría la métrica y erosionaría la fidelidad del nombre: el PQ-1
> debe **limpiar residuos reales**, no *ocultar* hallazgos al detector.