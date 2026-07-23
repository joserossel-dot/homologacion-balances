# Auditoría de Layouts del Parser — FASE 2A

**Fecha:** 2026-07-07 19:34:20

---

## Resumen General

- **Documentos analizados:** 186
  - PDF: 162
  - Excel: 24
- **Cuentas totales extraídas:** 30006
- **Documentos OCR:** 74 (39.8%)
- **Layouts distintos detectados:** 28

## Compatibilidad con ULTIMAS_COLS

| Estado | Documentos | % |
|--------|------------|---|
| ✅ SI | 58 | 31.2% |
| ❌ NO | 77 | 41.4% |
| ⚠️ PARCIAL | 27 | 14.5% |

## Catálogo de Layouts Detectados

| # | Layout | Documentos | Compatible | Riesgo Prom. | OCR |
|---|--------|------------|------------|--------------|-----|
| 1 | `SIN_HEADERS_DETECTADOS` | 60 | NO | 42.2 | 14 |
| 2 | `Deudor | Acreedor | Activo | Pasivo | Pérdida | Ganancia` | 37 | SI | 10.0 | 20 |
| 3 | `Activo | Pasivo` | 15 | NO | 54.3 | 13 |
| 4 | `Pasivo | Corriente | Corriente` | 15 | PARCIAL | 30.0 | 0 |
| 5 | `Debe | Haber | Deudor | Acreedor | Activo | Pasivo | Pérdida | Ganancia` | 13 | SI | 8.5 | 2 |
| 6 | `Activo | Pasivo | Patrimonio` | 5 | NO | 47.0 | 1 |
| 7 | `Activo | Neto` | 5 | NO | 51.0 | 1 |
| 8 | `Activo | Corriente | Pasivo | Corriente` | 4 | PARCIAL | 33.8 | 3 |
| 9 | `Pasivo | Patrimonio` | 4 | NO | 55.0 | 4 |
| 10 | `Pérdida | Ejercicio` | 4 | PARCIAL | 35.0 | 4 |
| 11 | `Saldo | Deudor | Saldo | Acreedor | Activo | Pasivo | Pérdida | Ganancia` | 3 | SI | 6.7 | 0 |
| 12 | `Activo | Corriente | Activo` | 3 | NO | 50.0 | 0 |
| 13 | `Activo | Pérdida | Ejercicio` | 2 | PARCIAL | 35.0 | 2 |
| 14 | `Activo | Pasivo | Pérdida | Ganancia` | 2 | SI | 0.0 | 0 |
| 15 | `Debe | Haber | Deudor | Activo | Pasivo | Pérdida` | 1 | NO | 55.0 | 1 |
| 16 | `Activo | Neto | Resultado | Ejercicio` | 1 | PARCIAL | 20.0 | 0 |
| 17 | `Saldo | Acreedor | Activo | Pasivo | Pérdida | Ganancia` | 1 | SI | 15.0 | 1 |
| 18 | `Gastos | Patrimonio` | 1 | NO | 55.0 | 1 |
| 19 | `Ingresos | Bruto | Pérdida` | 1 | NO | 55.0 | 1 |
| 20 | `Activo | Corriente` | 1 | NO | 55.0 | 1 |
| 21 | `Activo | Corriente | Pasivo` | 1 | NO | 55.0 | 1 |
| 22 | `Activo | Pasivo | Gastos | Ingresos` | 1 | PARCIAL | 20.0 | 0 |
| 23 | `Deudor | Activo | Pasivo | Pérdida` | 1 | NO | 55.0 | 1 |
| 24 | `Activo | Pasivo | Pérdida` | 1 | NO | 55.0 | 1 |
| 25 | `Acreedor | Pérdida` | 1 | NO | 55.0 | 1 |
| 26 | `Patrimonio | Neto | Capital` | 1 | NO | 40.0 | 0 |
| 27 | `Debe | Haber | Deudor | Activo | Pasivo | Pérdida | Ganancia` | 1 | SI | 15.0 | 1 |
| 28 | `Pasivo | Pérdida | Ganancia` | 1 | SI | 0.0 | 0 |

## Riesgo por Documento

### Top 20 documentos con mayor riesgo

| # | Archivo | Riesgo | Grupo | Compatible | Razón |
|---|---------|--------|-------|------------|-------|
| 1 | Balance 2019 FIRMADO.pdf | 80 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 2 | Balance General Año 2016 firmado.pdf | 80 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 3 | Balance Xpovin.pdf | 68 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Contaminación media (60%); No se detectaro |
| 4 | balance cm 2015.pdf | 68 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Contaminación media (62%); No se detectaro |
| 5 | balance cm 2016.pdf | 68 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Contaminación media (65%); No se detectaro |
| 6 | balance cm 2017.pdf | 68 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Contaminación media (55%); No se detectaro |
| 7 | Balance Capiro 2017-2018.pdf | 65 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 8 | Balance Clasificado 2016.pdf | 65 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 9 | Balance Tributario Chemo S.A Dic.2020.pdf | 65 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 10 | BALANCE DAIN 2015 hoja 2 (2).pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 11 | BALANCE SAN FELIX 2014-2015.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 12 | Balance Asipac 2015.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 13 | Balance Inmob 2015.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 14 | Balance Mega 2015.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 15 | Balance Sup Central 2015.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 16 | Balance de 8 columnas firmado año 2018.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 17 | PRE BALANCE AGRICOLA SAN SEBASTIAN.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 18 | Pre-Balance Comercializadora 2018.pdf | 65 | validacion | NO | Layout incompatible con ULTIMAS_COLS; Documento OCR — extracción menos confiable |
| 19 | BALANCE CLASIFICADO CENTRAL 2019.pdf | 60 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; No se detectaron encabezados de columna; A |
| 20 | Balance 12_2015.pdf | 60 | edge_cases | NO | Layout incompatible con ULTIMAS_COLS; No se detectaron encabezados de columna; A |

## Contaminación

- **Contaminación promedio:** 17.2%
- **Líneas totales procesadas:** 65699

### Top 10 documentos más limpios (menor contaminación)

- BALANCE CLASIFICADO CENTRAL 2019.pdf: **0.0%** (104 cuentas, 104 líneas)
- BALANCE DAIN 2015 hoja 1.pdf: **0.0%** (53 cuentas, 53 líneas)
- BALANCE DAIN 2015 hoja 2 (2).pdf: **0.0%** (31 cuentas, 31 líneas)
- Pre-Balance Comercializadora 2018.pdf: **0.4%** (259 cuentas, 259 líneas)
- PRE BALANCE AGRICOLA SAN SEBASTIAN.pdf: **0.6%** (172 cuentas, 172 líneas)
- Balance de 8 columnas firmado año 2018.pdf: **0.9%** (225 cuentas, 225 líneas)
- Pre Balance Tributario VFCH Dic 2019 v31.03.pdf: **1.4%** (361 cuentas, 361 líneas)
- pre-balance central 2016.pdf: **1.6%** (255 cuentas, 255 líneas)
- Balance 2018 con firma.pdf: **1.7%** (181 cuentas, 181 líneas)
- Pre Balance Tributario CASA Dic 2019 v31.03.pdf: **1.7%** (297 cuentas, 297 líneas)

### Top 10 documentos más contaminados

- balance cm 2016.pdf: **64.5%** (120 cuentas, 417 líneas)
- balance cm 2015.pdf: **61.8%** (166 cuentas, 553 líneas)
- Balance Xpovin.pdf: **59.8%** (401 cuentas, 1161 líneas)
- balance cm 2017.pdf: **54.5%** (232 cuentas, 576 líneas)
- Balance Chillan.xlsx: **44.4%** (11 cuentas, 18 líneas)
- Balance Viña Folatre.pdf: **41.0%** (609 cuentas, 3297 líneas)
- Balance Viña Folatre_146.pdf: **41.0%** (609 cuentas, 3297 líneas)
- Balance Viña Folatre_148.pdf: **41.0%** (609 cuentas, 3297 líneas)
- Balance Agrícola González Ltda.pdf: **41.0%** (600 cuentas, 3326 líneas)
- Balance Agrícola González Ltda_150.pdf: **41.0%** (600 cuentas, 3326 líneas)

## Calidad OCR

- **Documentos OCR:** 74
- **Páginas promedio:** 3.4
- **Cuentas promedio:** 123.9
- **Contaminación promedio OCR:** 13.5%

## Distribución por Grupo

- **edge_cases:** 97 documentos
- **validacion:** 89 documentos

## Archivos Generados

| Archivo | Descripción |
|---------|-------------|
| `layout_catalog.xlsx` | Catálogo completo de layouts agrupados por firma |
| `layout_summary.md` | Este resumen |
| `layout_statistics.json` | Métricas procesables en JSON |
| `layout_examples.xlsx` | Ejemplos representativos por layout |
| `layout_risk.xlsx` | Documentos ordenados por riesgo |
| `ocr_vs_native.xlsx` | Comparativa OCR vs texto nativo |
| `parser_contamination.xlsx` | Métricas de contaminación por documento |
| `recommended_layouts.json` | Layouts recomendados para FASE 2B |

---

## Conclusión

❌ **La heurística ULTIMAS_COLS solo es válida para el 31% de los documentos.**

### Desglose de la incompatibilidad

- **41% incompatible (77 documentos):** las columnas reales del balance
  no coinciden con [Activo, Pasivo, Pérdida, Ganancia]. El parser asigna
  montos a columnas incorrectas.
- **15% parcial (27 documentos):** algunas columnas coinciden
  pero no todas. Asignación parcialmente incorrecta.
- **34 documentos (18%) sin headers detectados:**
  no se pudo verificar la compatibilidad. Riesgo indeterminado.

### Principales layouts incompatibles

| Layout | Documentos | Problema |
|--------|------------|---------|
| `Activo | Pasivo` (balance sin ER) | 15 | Parser asigna a Pérdida/Ganancia |
| `Activo | Pasivo | Patrimonio` | 5 | Parser asigna a Pasivo/Pérdida/Ganancia |
| `Activo | Neto` | 5 | Columnas no estándar |
| `Pasivo | Corriente | Corriente` (EEFF) | 15 | Falsa detección — layout real tiene 4+ columnas |

### Impacto en FASE 2B

El nuevo parser orientado por layout debe detectar automáticamente:
1. **Formato 8 columnas** (Debe/Haber + Deudor/Acreedor + Act/Pas/Per/Gan) → 13 docs
2. **Formato 6 columnas** (Deudor/Acreedor + Act/Pas/Per/Gan) → 37 docs
3. **Formato 4 columnas** (Act/Pas/Per/Gan estándar) → 58+ docs
4. **Formato 2 columnas** (solo Act/Pas, sin ER) → ~15 docs
5. **Excel** (sin detección de columnas) → 24 docs
6. **Formato EEFF** (Activo Corriente/No Corriente/Pasivo Corriente/No Corriente/Patrimonio) → ~15 docs

Además, para ~60 documentos (32%) no se detectaron headers explícitos —
el parser deberá inferir el layout desde la estructura de la tabla.
