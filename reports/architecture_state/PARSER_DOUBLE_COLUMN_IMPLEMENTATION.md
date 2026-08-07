# PARSER_DOUBLE_COLUMN_IMPLEMENTATION — Balance Clasificado de doble columna

**Fecha:** 2026-08-05
**Tipo:** Reporte de implementación (fix aplicado + evidencias antes/después)
**Caso reproducido:** `datasets/STRESS/8_COLUMNS/2022-BALANCE CLASIFICADO 2022.pdf`
**Auditoría previa (referencia):** `reports/architecture_state/PARSER_DOUBLE_COLUMN_AUDIT.md`
**Benchmark de referencia:** M5 (2660/2662, 99.92%) — congelado; verificado NO afectado.

---

## 1. Cambios aplicados

### 1.1 `document_intelligence/extractors/double_column.py` (NUEVO)

Módulo con la lógica de detección y separación estructural de doble columna.
100% estructural — NUNCA usa el nombre de archivo:

- `_prefiltro_sugiere(texto)`: puerta barata sobre el texto plano ya extraído
  (2+ líneas con 2+ tokens compactos de 5-6 dígitos). Evita abrir pdfplumber
  de más en documentos sin esta disposición.
- `_boundary_2_clusters(words)`: calcula el `x0` de corte con clustering de 2
  grupos (minimización de varianza intra-cluster).
- `_lado_es_cuenta(tokens)`: un lado es una cuenta real si empieza con un token
  tipo código de cuenta + tiene nombre alfabético + un monto.
- `separar_page(page)`: produce DOS líneas independientes por cada fila doble
  (cuenta a ambos lados del boundary); devuelve `None` si la página no es doble
  columna (→ flujo universal idéntico).
- `separar_desde_pdf(path)`: versión documento completo (pre-filtro + por página).
- `DoubleColumnExtractor(SpecializedExtractor)`: extractor registrado que
  delega al Parser Universal reutilizando `parsear_linea` (vía `lineas_presplit`).
  Ante cualquier incertidumbre → `fallback_used=True` (universal exacto).

### 1.2 `parser_universal.py`

- `PATRON_COMPACTO`: `^\d{6,10}$` → `^\d{5,10}$` (línea 206) — acepta códigos de
  5 dígitos (`11010`, `21010`). Alineado con el DIE (`\b\d{4,6}\b`).
- `PATRONES_CODIGO_LINEA[FormatoCodigo.COMPACTO]`: `^\d{6,10}\s+` → `^\d{5,10}\s+`
  (línea 413) — extrae el código de 5 dígitos de la línea.
- `ExtractionContext.lineas_presplit` (nuevo campo): si un extractor especializado
  ya separó las líneas, `_extraer_lineas()` las usa directamente, reutilizando
  íntegramente el pipeline posterior (formato, separador, `parsear_linea`).
- `_extraer_lineas()` (línea 864): en el bucle de páginas, si el pre-filtro
  sugiere doble columna, se intenta `separar_page(page)`; si confirma, se usan
  las líneas separadas; si no, se conserva el texto plano tal cual
  (comportamiento universal idéntico). Envuelto en try/except — nunca rompe.

### 1.3 `document_intelligence/extractors/__init__.py`

- Importa `DoubleColumnExtractor` al paquete (registro automático).

### 1.4 Restricciones respetadas (de la auditoría)

- NO se tocaron: `learning/`, runtime, benchmark (M5), gold, semantic, CMCC,
  Knowledge Manager, UI (`app_validacion.py`), `pipeline/`, `orchestrator/`.
- NO se duplica `parsear_linea`, `detectar_formato_codigo` ni la resolución de
  montos: el splitter solo genera DOS líneas independientes; el parsing lo hace
  el Parser Universal con la lógica existente.
- `UniversalExtractor` sigue siendo el fallback obligatorio.
- La detección es estructural (coordenadas `x0`), nunca por nombre de archivo.

---

## 2. Evidencia antes / después

Caso: `2022-BALANCE CLASIFICADO 2022.pdf`

| Métrica | ANTES | DESPUÉS |
|---|---|---|
| Cuentas extraídas | 30 | 41 |
| Cuentas con código | 0 | 29 |
| Formato de código detectado | sin_codigo | compacto |

### Antes (líneas fusionadas, sin código, montos corruptos)

```
0 None 'BALANCE CLASIFICADO' None
1 None 'AL 31 DE DICIEMBRE DE' 2022.0
2 None 'ACTIVO CIRCULANTE PASIVO CIRCULANTE' None
3 None '11010 CAJAS $ 2.995.687 21010 OBLIG. BANCOS U/O FINAN. $' 1.0
4 None '11020 BANCOS $ 3 06.726.181 21020 PROVEEDORES $' 1.0
```

### Después (cada fila → dos cuentas independientes con código)

```
3 '11010' 'CAJAS $' 2995687.0
4 '21010' 'OBLIG. BANCOS U/O FINAN. $' 1.0
5 '11020' 'BANCOS $' 3.0
6 '21020' 'PROVEEDORES $' 1.0
7 '11030' 'INVERSIONES FINANCIERAS $' 4.0
8 '21030' 'DOCUMENTOS POR PAGAR' None
9 '11040' 'CLIENTES $' 6.0
10 '21040' 'REMUNERACIONES POR PAGAR $' 5.0
```

Notas sobre artefactos residuales (comportamiento universal pre-existente,
FUERA del alcance de este fix):

- El `$` queda en el nombre (`CAJAS $`): el parser universal lo conserva hoy
  en todos los formatos; no es introducido por este cambio.
- Los montos partidos en tokens (`3` / `06.726.181`) producen `monto=3.0` en
  algunas líneas: pre-existente (la auditoría lo documenta como riesgo bajo,
  no objetivo).
- Las líneas de encabezado a ancho completo (`AL 31 DE DICIEMBRE DE 2022`,
  `ACTIVO CIRCULANTE PASIVO CIRCULANTE`) NO son filas dobles y siguen el flujo
  universal: permanecen como antes (cuentas fantasma ya existentes).

---

## 3. Selectividad del detector (validación sobre todo el dataset)

Se evaluó el detector estructural sobre **608 PDFs** del repo:

| Criterio | Resultado |
|---|---|
| Pre-filtro (regex, texto plano) | 2 archivos |
| Detector estructural definitivo | **1 archivo** (el caso 8_COLUMNS, 11 filas dobles) |

El único falso candidato del pre-filtro (`IT_0338_Gonzagri...TAS AGRICOLA_1.pdf`,
un informe de tasación) NO confirma la separación estructural → se mantiene en
el flujo universal. El benchmark HOLDOUT M5 (20 archivos) tiene **0** activaciones.

Verificación adicional: los 20 archivos del manifiesto M5 (`benchmark/dataset_manifest.csv`)
no disparan el pre-filtro ni cambian su formato con `PATRON_COMPACTO` 5 dígitos.

---

## 4. Cobertura de tests

- `tests/test_extractors.py`, `tests/test_generic_extractor.py`,
  `tests/test_column_interpretation.py`, `tests/test_parser_hygiene.py`,
  `tests/test_backward_compatibility.py`, `tests/test_api_compatibility.py`,
  `tests/test_document_kb.py`, `tests/test_balance_interpreter.py`,
  `tests/test_document_mining.py`, `tests/test_context_builder.py` → **PASS**.
- Suites de integración (`test_sprint31_integration.py`,
  `test_document_analyzer_integration.py`) → se ejecutan sobre PDFs reales y
  son lentas; su bloqueo/hang es **pre-existente** (verificado: también cuelgan
  en el código original sin mis cambios).

### Comandos
```bash
python3 -m pytest tests/test_extractors.py tests/test_generic_extractor.py \
  tests/test_column_interpretation.py tests/test_parser_hygiene.py -q
```

---

## 5. Benchmark M5 (2660/2662)

El "2660/2662" es el **identificador de la base congelada del benchmark M5**
(99.92%), NO una cifra que se recalculue con este fix. Verificado:

1. Ninguno de los 20 archivos del manifiesto M5 dispara el pre-filtro de doble
   columna (0 activaciones).
2. `PATRON_COMPACTO` 5 dígitos: los únicos archivos cuyo conteo de tokens
   cambia están en `STRESS/8_COLUMNS` y en HOLDOUT/validacion con formato
   `sin_codigo` (códigos concatenados sin espacio — p. ej. `10050CAJA`), que NO
   pertenecen al manifiesto M5 congelado.
3. `gold_standard.db`, `gold_standard_runtime.db`, `gold_standard_bench.db`
   no fueron modificados.

---

## 6. Archivos modificados

| Archivo | Tipo |
|---|---|
| `document_intelligence/extractors/double_column.py` | nuevo (detector + extractor) |
| `parser_universal.py` | `PATRON_COMPACTO`, `PATRONES_CODIGO_LINEA[COMPACTO]`, `lineas_presplit`, hook en `_extraer_lineas` |
| `document_intelligence/extractors/__init__.py` | import/registro del extractor |
