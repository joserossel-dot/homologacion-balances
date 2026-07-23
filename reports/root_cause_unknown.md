# Root-Cause Analysis — DEv2 UNKNOWN Accounts

**Date:** 2026-07-22  
**Total UNKNOWN:** 5392 accounts  
**Source:** `decision_engine_shadow.json` — DEv2 shadow run on 11,690 accounts  

---

## Executive Summary

Of 5392 UNKNOWN accounts, the root causes distribute as follows. Each account is assigned to exactly ONE root cause.

**Quick wins (ROI ≥ 20):** categories where fixing 1 concept resolves 20+ accounts.  
**Long tail (ROI < 5):** categories requiring per-account effort.

---

## Pareto Analysis (sorted by ROI)

| # | Categoria | Cuentas | % | Acumulado % | Esfuerzo (1-5) | ROI | Descripción |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | parser | 1167 | 21.6% | 50.9% | 2 | 10.8 | Datos de parser embebidos en el nombre (folios, RUTs, montos, fechas) — 1167 cuentas (21.6%) |
| 2 | concepto inexistente | 1576 | 29.2% | 29.2% | 4 | 7.3 | Nombre limpio en espanol no cubierto por el catalogo — 1576 cuentas (29.2%) |
| 3 | empresa | 396 | 7.3% | 79.5% | 1 | 7.3 | Razones sociales, direcciones, datos de empresa — 396 cuentas (7.3%) |
| 4 | abreviatura | 544 | 10.1% | 72.1% | 2 | 5.0 | Abreviaturas no estandarizadas (PROV., SERV., GTA., etc.) — 544 cuentas (10.1%) |
| 5 | ruido | 217 | 4.0% | 89.6% | 1 | 4.0 | Lineas estructurales PDF, encabezados, pies de pagina, totales — 217 cuentas (4.0%) no son cuentas reales |
| 6 | catálogo incompleto | 601 | 11.1% | 62.0% | 3 | 3.7 | Variantes ortograficas o nombres cercanos a conceptos existentes — 601 cuentas (11.1%) |
| 7 | sigla | 124 | 2.3% | 99.6% | 1 | 2.3 | Acronimos sin expansion en catalogo (AFP, IVA, PPM, etc.) — 124 cuentas (2.3%) |
| 8 | OCR | 329 | 6.1% | 85.6% | 3 | 2.0 | Artefactos de OCR (basura inicial, palabras fusionadas, sustituciones digito/letra) — 329 cuentas (6.1%) |
| 9 | cuenta tributaria | 207 | 3.8% | 97.3% | 2 | 1.9 | Conceptos tributarios sin cobertura en catalogo — 207 cuentas (3.8%) |
| 10 | cuenta compuesta | 208 | 3.9% | 93.4% | 3 | 1.3 | Dos conceptos unidos por 'Y' que deberian separarse — 208 cuentas (3.9%) |
| 11 | nombre propio | 21 | 0.4% | 100.0% | 1 | 0.4 | Nombres de personas usados como cuentas — 21 cuentas (0.4%) |
| 12 | error humano | 2 | 0.0% | 100.0% | 1 | 0.0 | Errores de tipeo en el PDF original — 2 cuentas (0.0%) |

---

## Category Details

### Parser (1167 · 21.6%)

Datos de parser embebidos en el nombre (folios, RUTs, montos, fechas) — 1167 cuentas (21.6%)

**Sub-causas:**

- `montos_embebidos`: 939 cuentas
- `fecha_embebida`: 117 cuentas
- `rut_embebido`: 57 cuentas
- `porcentaje_embebido`: 29 cuentas
- `folio_embebido`: 25 cuentas

**Muestras:**

- `GM ———omeccion AVDA. LOSCONQUISTADORES 1700 FOLIO UNICO NACI` → El nombre contiene 'Folio': 'GM ———omeccion AVDA. LOSCONQUISTADORES 1700 FOLIO '
- `o DIRECCION AVDA, LOS CONQUISTADORES 1700 FOLIO UNICO NACION` → El nombre contiene 'Folio': 'o DIRECCION AVDA, LOS CONQUISTADORES 1700 FOLIO UN'
- `(AAA a 85d DIDIROMA ALA AN Folio` → El nombre contiene 'Folio': '(AAA a 85d DIDIROMA ALA AN Folio'
- `| REMUNERACIONESPOR — 856.159.690 970.6050%4` → El nombre contiene 3 montos: '| REMUNERACIONESPOR — 856.159.690 970.6050%4'
- `O Cs omecaioN AVDA. LOSCONQUISTADORES 1700 FOLIO UNICO NACIO` → El nombre contiene 'Folio': 'O Cs omecaioN AVDA. LOSCONQUISTADORES 1700 FOLIO U'
- `_AAMMM>+=]=21029 mm de 01/00 A RON Folio` → El nombre contiene 'Folio': '_AAMMM>+=]=21029 mm de 01/00 A RON Folio'
- `MO. CONTRATISTA 339.294.130 221200 339.572.930 :` → El nombre contiene 2 montos: 'MO. CONTRATISTA 339.294.130 221200 339.572.930 :'
- `o FERIADO PROPORCIONAL — 38.826.788 158.375 38.668.415 ]` → El nombre contiene 3 montos: 'o FERIADO PROPORCIONAL — 38.826.788 158.375 38.668
- `OTROS GASTOS DEL 997 682 ? 997.582 :` → El nombre contiene 3 montos: 'OTROS GASTOS DEL 997 682 ? 997.582 :'
- `MANTENCION Y 103.795.303 108.793.303 :` → El nombre contiene 2 montos: 'MANTENCION Y 103.795.303 108.793.303 :'
- ... and 1157 more

---

### Concepto Inexistente (1576 · 29.2%)

Nombre limpio en espanol no cubierto por el catalogo — 1576 cuentas (29.2%)

**Sub-causas:**

- `concepto_limpio`: 1576 cuentas

**Muestras:**

- `INSUMOS PLANTA` → Concepto limpio no cubierto por catalogo: 'INSUMOS PLANTA'
- `ad INSUMOS QUIMICOS` → Concepto limpio no cubierto por catalogo: 'ad INSUMOS QUIMICOS'
- `ARTICULOS DE ASEO` → Concepto limpio no cubierto por catalogo: 'ARTICULOS DE ASEO'
- `had : ROPA DE TRABAJO` → Concepto limpio no cubierto por catalogo: 'had : ROPA DE TRABAJO'
- `E FROVISION PLANTA` → Concepto limpio no cubierto por catalogo: 'E FROVISION PLANTA'
- `SEGURO DE INVALIDEZ` → Concepto limpio no cubierto por catalogo: 'SEGURO DE INVALIDEZ'
- `TRANSPORTE PERSONAL —` → Concepto limpio no cubierto por catalogo: 'TRANSPORTE PERSONAL —'
- `GAS LICUADO` → Concepto limpio no cubierto por catalogo: 'GAS LICUADO'
- `QUIMICOS CEREZAS` → Concepto limpio no cubierto por catalogo: 'QUIMICOS CEREZAS'
- `INSUMOS QUIMICOS` → Concepto limpio no cubierto por catalogo: 'INSUMOS QUIMICOS'
- ... and 1566 more

---

### Empresa (396 · 7.3%)

Razones sociales, direcciones, datos de empresa — 396 cuentas (7.3%)

**Sub-causas:**

- `razon_social`: 383 cuentas
- `direccion`: 13 cuentas

**Muestras:**

- `CAPTRO CHILE SPA PAGINA:` → Razon social: 'CAPTRO CHILE SPA PAGINA:'
- `CAPIRO CHILE SPA : : PAGINA:` → Razon social: 'CAPIRO CHILE SPA : : PAGINA:'
- `Cta. Cte. Termas de Jahuel SA` → Razon social: 'Cta. Cte. Termas de Jahuel SA'
- `Cta. Cte. Inversiones Malaga SA LP` → Razon social: 'Cta. Cte. Inversiones Malaga SA LP'
- `Ganancia (Perdida) Chemo SA` → Razon social: 'Ganancia (Perdida) Chemo SA'
- `Ganancia (Perdida) Chemopharma SA` → Razon social: 'Ganancia (Perdida) Chemopharma SA'
- `Ganancia (Perdida) Embotelladora Jahuel SA` → Razon social: 'Ganancia (Perdida) Embotelladora Jahuel SA'
- `Gananci (Perdida) Quilicura SA` → Razon social: 'Gananci (Perdida) Quilicura SA'
- `Ganancia (Perdida) Termas de Jahuel SA` → Razon social: 'Ganancia (Perdida) Termas de Jahuel SA'
- `Cta. Cte. Cia. de Inverisones La Central SA` → Razon social: 'Cta. Cte. Cia. de Inverisones La Central SA'
- ... and 386 more

---

### Abreviatura (544 · 10.1%)

Abreviaturas no estandarizadas (PROV., SERV., GTA., etc.) — 544 cuentas (10.1%)

**Sub-causas:**

- `abreviatura_no_reconocida`: 369 cuentas
- `abreviatura_conocida`: 175 cuentas

**Muestras:**

- `E OBRAS B. INMUEBLE` → Abreviatura(s) no estandar: B. en: 'E OBRAS B. INMUEBLE'
- `OBRAS B. MUEBLES 108.963.751 4A80D00 —` → Abreviatura(s) no estandar: B. en: 'OBRAS B. MUEBLES 108.963.751 4A80D00 —'
- `SERV. DE TERCEROS` → Abreviatura(s): SERV. en: 'SERV. DE TERCEROS'
- `Oo. ANIVEL` → Abreviatura(s) no estandar: Oo. en: 'Oo. ANIVEL'
- `E ARTICULOS LIBRERIA 6301958 77.080 6324878 :` → Abreviatura(s) no estandar: 77.080 en: 'E ARTICULOS LIBRERIA 6301958 77.080 6324
- `Mat. Prepar. Vitrinas (Visual)` → Abreviatura(s) no estandar: Mat., Prepar. en: 'Mat. Prepar. Vitrinas (Visual)'
- `RICARDO RAFAEL ABAD GARCAI CTA.PAR` → Abreviatura(s) no estandar: CTA.PAR en: 'RICARDO RAFAEL ABAD GARCAI CTA.PAR'
- `per [Presses ins O enserio san Peza as act compas dados. |` → Abreviatura(s) no estandar: dados. en: 'per [Presses ins O enserio san Peza as a
- `PAGO PROV. POR UTIL. ABSORBIDAS 19.157.394 CUENTAS POR PAGAR` → Abreviatura(s): PROV. en: 'PAGO PROV. POR UTIL. ABSORBIDAS 19.157.394 CUENTAS'
- `Activo Circulante 6.333.007.743 RAFAEL ABAD GARCIA, CTA. PAR` → Abreviatura(s) no estandar: CTA. en: 'Activo Circulante 6.333.007.743 RAFAEL ABA
- ... and 534 more

---

### Ruido (217 · 4.0%)

Lineas estructurales PDF, encabezados, pies de pagina, totales — 217 cuentas (4.0%) no son cuentas reales

**Sub-causas:**

- `encabezado_pie`: 72 cuentas
- `no_clasificado`: 57 cuentas
- `estructura_pdf`: 50 cuentas
- `solo_numeros`: 28 cuentas
- `insuficiente`: 10 cuentas

**Muestras:**

- `Nivel` → Texto de encabezado/pie de pagina: 'Nivel'
- `Desde Enero a Diciembre` → Texto de encabezado/pie de pagina: 'Desde Enero a Diciembre'
- `Desde 01/01/2014 — Al 3112014 NW” Folio` → Texto de encabezado/pie de pagina: 'Desde 01/01/2014 — Al 3112014 NW” Folio'
- `l Total Párina` → Elemento estructural PDF: 'l Total Párina'
- `Desde 01/01/2014 Al 31/12/2014 N' Folio` → Texto de encabezado/pie de pagina: 'Desde 01/01/2014 Al 31/12/2014 N' Folio'
- `Dela Página Anterior` → Texto de encabezado/pie de pagina: 'Dela Página Anterior'
- `Desde 01/01/2014 Aa 31/12/2014 N" Folio` → Texto de encabezado/pie de pagina: 'Desde 01/01/2014 Aa 31/12/2014 N" Folio'
- `: De la Página Anterior` → Elemento estructural PDF: ': De la Página Anterior'
- `Desde 01/01/3014 — Al 31/12£0014 WN" Folio` → Texto de encabezado/pie de pagina: 'Desde 01/01/3014 — Al 31/12£0014 WN" Folio'
- `Dela Página Anterior —` → Texto de encabezado/pie de pagina: 'Dela Página Anterior —'
- ... and 207 more

---

### Catálogo Incompleto (601 · 11.1%)

Variantes ortograficas o nombres cercanos a conceptos existentes — 601 cuentas (11.1%)

**Sub-causas:**

- `no_cubierto`: 587 cuentas
- `variante_ortografica`: 14 cuentas

**Muestras:**

- `A _ — — á+>=>=+=—=2211 aa ed DOOM ANP FOdio` → Nombre con contenido pero no en catalogo: 'A _ — — á+>=>=+=—=2211 aa ed DOOM ANP
- `CAMARAS` → Nombre con contenido pero no en catalogo: 'CAMARAS'
- `ARRIENDO CAMARA 16.677.603 —` → Nombre con contenido pero no en catalogo: 'ARRIENDO CAMARA 16.677.603 —'
- `E CONTROL DE CALIDAD 39.239.468 —` → Nombre con contenido pero no en catalogo: 'E CONTROL DE CALIDAD 39.239.468 —'
- `ARRIENDO BINS 1487359 —` → Nombre con contenido pero no en catalogo: 'ARRIENDO BINS 1487359 —'
- `17) i £NALISIS LABORATORIO` → Nombre con contenido pero no en catalogo: '17) i £NALISIS LABORATORIO'
- `— | [23 frobicerrasvo "| ress2g0543 zo Fsstanafinal` → Nombre con contenido pero no en catalogo: '— | [23 frobicerrasvo "| ress2g0543 z
- `717857|699 [fevos ques dañe agora RU gin TRA` → Nombre con contenido pero no en catalogo: '717857|699 [fevos ques dañe agora RU 
- `1231890459/8814 Jonaés dota Desea` → Nombre con contenido pero no en catalogo: '1231890459/8814 Jonaés dota Desea'
- `73 TOTAL A PAGAR (Líneas` → Nombre con contenido pero no en catalogo: '73 TOTAL A PAGAR (Líneas'
- ... and 591 more

---

### Sigla (124 · 2.3%)

Acronimos sin expansion en catalogo (AFP, IVA, PPM, etc.) — 124 cuentas (2.3%)

**Sub-causas:**

- `sigla_reconocida`: 124 cuentas

**Muestras:**

- `O: ANIVEL` → Sigla(s): ANIVEL
- `E CASINO` → Sigla(s): CASINO
- `i ARMADO DE CAJAS` → Sigla(s): ARMADO, DE, CAJAS
- `€ CASINO` → Sigla(s): CASINO
- `ARMADO CAJAS PLANTA` → Sigla(s): ARMADO, CAJAS, PLANTA
- `FORM` → Sigla(s): FORM
- `FORM` → Sigla(s): FORM
- `LONG TERM DEBT` → Sigla(s): LONG, TERM, DEBT
- `OTHERS LONG TERM` → Sigla(s): OTHERS, LONG, TERM
- `O: ANIVEL` → Sigla(s): ANIVEL
- ... and 114 more

---

### Ocr (329 · 6.1%)

Artefactos de OCR (basura inicial, palabras fusionadas, sustituciones digito/letra) — 329 cuentas (6.1%)

**Sub-causas:**

- `basura_inicial`: 291 cuentas
- `solo_digitos`: 35 cuentas
- `minuscula_inicial`: 3 cuentas

**Muestras:**

- `| GTA. CTE SOCIOS` → Basura inicial '| ' en: '| GTA. CTE SOCIOS' -> 'GTA. CTE SOCIOS'
- `l ANTICIFO PERSONAL:` → Basura inicial 'l ' en: 'l ANTICIFO PERSONAL:' -> 'ANTICIFO PERSONAL:'
- `e SALA CUNA` → Basura inicial 'e ' en: 'e SALA CUNA' -> 'SALA CUNA'
- `o FILES PLANTA` → Basura inicial 'o ' en: 'o FILES PLANTA' -> 'FILES PLANTA'
- `o OTROS GASTOS E` → Basura inicial 'o ' en: 'o OTROS GASTOS E' -> 'OTROS GASTOS E'
- `0 —ANIVEL` → Basura inicial '0 ' en: '0 —ANIVEL' -> '—ANIVEL'
- `: BOMBAS Y MOTORES` → Basura inicial ': ' en: ': BOMBAS Y MOTORES' -> 'BOMBAS Y MOTORES'
- `: VARIOS DEUDORESLP. '` → Basura inicial ': ' en: ': VARIOS DEUDORESLP. '' -> 'VARIOS DEUDORESLP. ''
- `o. FONASA` → Basura inicial 'o' en: 'o. FONASA' -> '. FONASA'
- `o PROV.COMPRA FRUTA` → Basura inicial 'o ' en: 'o PROV.COMPRA FRUTA' -> 'PROV.COMPRA FRUTA'
- ... and 319 more

---

### Cuenta Tributaria (207 · 3.8%)

Conceptos tributarios sin cobertura en catalogo — 207 cuentas (3.8%)

**Sub-causas:**

- `tributaria_iva`: 54 cuentas
- `tributaria_impuesto`: 30 cuentas
- `tributaria_impuestos`: 27 cuentas
- `tributaria_cesantia`: 21 cuentas
- `tributaria_renta`: 17 cuentas
- `tributaria_tributario`: 14 cuentas
- `tributaria_credito`: 8 cuentas
- `tributaria_trabajadores`: 7 cuentas
- `tributaria_segunda`: 5 cuentas
- `tributaria_tributaria`: 5 cuentas
- `tributaria_sence`: 5 cuentas
- `tributaria_retencion`: 4 cuentas
- `tributaria_ppm`: 3 cuentas
- `tributaria_cesantía`: 2 cuentas
- `tributaria_fiscal`: 2 cuentas
- `tributaria_p.p.m.`: 1 cuentas
- `tributaria_retención`: 1 cuentas
- `tributaria_i.v.a.`: 1 cuentas

**Muestras:**

- `FONDOS CESANTIA` → Concepto tributario: 'FONDOS CESANTIA'
- `SEGUNDA CATEGORÍA` → Concepto tributario: 'SEGUNDA CATEGORÍA'
- `SEGURO CESANTIA` → Concepto tributario: 'SEGURO CESANTIA'
- `REPUBLICA DE CHILE AÑO TRIBUTARIO 07 N*` → Concepto tributario: 'REPUBLICA DE CHILE AÑO TRIBUTARIO 07 N*'
- `REPUBLICA DE CHILE AÑO TRIBUTARIO 07 N”` → Concepto tributario: 'REPUBLICA DE CHILE AÑO TRIBUTARIO 07 N”'
- `Impuesto de Timbres` → Concepto tributario: 'Impuesto de Timbres'
- `REMANENTE CREDITO FISCAL a 216356 a 216356 8 a` → Concepto tributario: 'REMANENTE CREDITO FISCAL a 216356 a 216356 8 a'
- `SEGURO CESANTIA 1011805 1076814 a £4089 a 64289 ]` → Concepto tributario: 'SEGURO CESANTIA 1011805 1076814 a £4089 a 64289 ]'
- `SEGURO CESANTIA` → Concepto tributario: 'SEGURO CESANTIA'
- `INPTO.RENTA 10CAT6` → Concepto tributario: 'INPTO.RENTA 10CAT6'
- ... and 197 more

---

### Cuenta Compuesta (208 · 3.9%)

Dos conceptos unidos por 'Y' que deberian separarse — 208 cuentas (3.9%)

**Sub-causas:**

- `union_y`: 208 cuentas

**Muestras:**

- `PERDIDAS Y GANANCIAS —` → Cuenta compuesta con 'Y': 'PERDIDAS Y GANANCIAS —'
- `RAZON SOC Pascicing y Servicios Rucsray` → Cuenta compuesta con 'Y': 'RAZON SOC Pascicing y Servicios Rucsray'
- `PEAJES Y 1.127.329 Ñ` → Cuenta compuesta con 'Y': 'PEAJES Y 1.127.329 Ñ'
- `72 MAS: Intereses y Multas` → Cuenta compuesta con 'Y': '72 MAS: Intereses y Multas'
- `72 MAS: intereses y Multas` → Cuenta compuesta con 'Y': '72 MAS: intereses y Multas'
- `Ambientación y Audio` → Cuenta compuesta con 'Y': 'Ambientación y Audio'
- `Ambientación y Audio` → Cuenta compuesta con 'Y': 'Ambientación y Audio'
- `UTILES Y ENSERES` → Cuenta compuesta con 'Y': 'UTILES Y ENSERES'
- `ÚTILES Y ENSERES` → Cuenta compuesta con 'Y': 'ÚTILES Y ENSERES'
- `Otros Documento y Cuentas por Pagar` → Cuenta compuesta con 'Y': 'Otros Documento y Cuentas por Pagar'
- ... and 198 more

---

### Nombre Propio (21 · 0.4%)

Nombres de personas usados como cuentas — 21 cuentas (0.4%)

**Sub-causas:**

- `tratamiento`: 21 cuentas

**Muestras:**

- `586.708.125 Sr. Sebastián García Tagle ($)` → Nombre personal con tratamiento: '586.708.125 Sr. Sebastián García Tagle ($)'
- `Cta. En Part. Inmob. Don Alberto ($)` → Nombre personal con tratamiento: 'Cta. En Part. Inmob. Don Alberto ($)'
- `Cta. En Part. Inmob. Don Jaime ($)` → Nombre personal con tratamiento: 'Cta. En Part. Inmob. Don Jaime ($)'
- `13210-0000 INMOBILIARIA FUNDADOR DON` → Nombre personal con tratamiento: '13210-0000 INMOBILIARIA FUNDADOR DON'
- `13211-0000 INMOBILIARIA FUNDADOR DON JAIME` → Nombre personal con tratamiento: '13211-0000 INMOBILIARIA FUNDADOR DON JAIME'
- `13212-0000 INMOBILIARIA FUNDADOR DON DANIEL` → Nombre personal con tratamiento: '13212-0000 INMOBILIARIA FUNDADOR DON DANIEL'
- `13229-0000 CTA. EN PARTICIPACION INMOB. DON` → Nombre personal con tratamiento: '13229-0000 CTA. EN PARTICIPACION INMOB. DON'
- `13230-0000 CTA. EN PART. INMOB. DON ALBERTO` → Nombre personal con tratamiento: '13230-0000 CTA. EN PART. INMOB. DON ALBERTO'
- `Cta. En Part. Inmob. Don Sergio` → Nombre personal con tratamiento: 'Cta. En Part. Inmob. Don Sergio'
- `Cta. En Part. Inmob. Don Alberto` → Nombre personal con tratamiento: 'Cta. En Part. Inmob. Don Alberto'
- ... and 11 more

---

### Error Humano (2 · 0.0%)

Errores de tipeo en el PDF original — 2 cuentas (0.0%)

**Sub-causas:**

- `tipo`: 2 cuentas

**Muestras:**

- `EMDICATO` → Posible typo: EMDICATO -> MEDICATO: 'EMDICATO'
- `EMDICATO` → Posible typo: EMDICATO -> MEDICATO: 'EMDICATO'

---


## Recommendations

### Phase 1 — No-code fixes (ROI > 10)

| Category | Action | Impact |
|---|---|---|
| parser | Mejorar parser para extraer solo el nombre de cuenta, no datos adjuntos | -21.6% UNKNOWN |

### Phase 2 — Catalog & regex (ROI 5-10)

| Category | Action | Impact |
|---|---|---|
| concepto inexistente | Ampliar catalogo de conceptos con ~200-300 nuevas entradas | -29.2% UNKNOWN |
| empresa | Filtrar razones sociales del pipeline de clasificacion (no son cuentas contables) | -7.3% UNKNOWN |
| abreviatura | Crear diccionario de abreviaturas (~80 entradas) con expansion automatica | -10.1% UNKNOWN |

### Phase 3 — Long tail (ROI < 5)

| Category | Action | Impact |
|---|---|---|
| ruido | Agregar filtro de lineas estructurales PDF en preprocesamiento (Nivel, Desde, Folio, Página, Total) | -4.0% UNKNOWN |
| catálogo incompleto | Agregar variantes ortograficas y sinonimos al catalogo existente (~150 entradas) | -11.1% UNKNOWN |
| sigla | Agregar ~50 siglas al catalogo con su expansion | -2.3% UNKNOWN |
| OCR | Agregar pipeline de limpieza OCR: eliminar basura inicial, separar palabras fusionadas, corregir sustituciones | -6.1% UNKNOWN |
| cuenta tributaria | Agregar ~30 conceptos tributarios faltantes al catalogo | -3.8% UNKNOWN |
| cuenta compuesta | Dividir cuentas compuestas en dos conceptos separados | -3.9% UNKNOWN |
| nombre propio | Filtrar o normalizar nombres de personas (bajo ROI, mantener como UNKNOWN) | -0.4% UNKNOWN |
| error humano | Implementar corrector ortografico basico para variantes conocidas | -0.0% UNKNOWN |

---

## Methodology

Each of the 5,392 UNKNOWN accounts was classified into exactly one root cause using rule-based detection:

1. **ruido** — regex detection of PDF structural elements (Nivel, Desde, Folio, Página, Total, fechas solas)
2. **parser** — detection of embedded parser artifacts (RUTs, amounts, dates in account names)
3. **OCR** — leading garbage characters, merged words, digit-letter substitutions
4. **empresa** — company suffixes (SA, Ltda, EIRL, SPA), addresses
5. **nombre propio** — honorifics, personal names
6. **sigla** — known Chilean acronyms (AFP, IVA, PPM, FONASA, etc.)
7. **abreviatura** — words with periods, known abbreviations
8. **cuenta tributaria** — tax keywords (impuesto, ppm, iva, retención)
9. **cuenta compuesta** — two concepts joined by 'Y'
10. **catálogo incompleto** — near-miss variants of existing concepts
11. **regex faltante** — patterns detectable by regex (GASTOS DE ..., PROVISION ...)
12. **concepto inexistente** — clean Spanish names not covered
13. **error humano** — typos, misspellings
14. **ruido (fallback)** — unclassifiable garbage

**Note:** Categories are mutually exclusive. Classification priority follows the order above. Some accounts in lower-priority categories might also have characteristics of higher-priority ones.

