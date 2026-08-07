# PQ-2 · Análisis de causa raíz — CODIGO_PERDIDO (taxonomía de los 2.755)

> **Fase 2.1 del PQ-2 (recomendado como siguiente objetivo en `PQ2_PRIORITY_ANALYSIS.md`).**
> Este documento hace la **caracterización causa‑raíz completa de CODIGO_PERDIDO** antes de
> proponer cualquier cambio. Es **auditoría/medición únicamente**: **no se modificó código**.
>
> **Base exclusiva:** baseline **PQ-0 congelado** (`reports/parser_quality/baselines/PQ0/`,
> `PQ0_findings.csv` + `PQ0_dataset.csv`), commit `dca065578f80…`. Cada hallazgo se etiquetó a un
> único patrón con un clasificador determinista. Se leyó `parsear_linea` y `PATRONES_CODIGO_LINEA`
> en `parser_universal.py` (solo lectura) para explicar *por qué* falla la extracción.

---

## 0. Pregunta raíz

**¿Por qué 2.755 líneas que empiezan con algo que parece un código de cuenta quedan con `codigo = None`?**

La respuesta está en dos niveles que se refuerzan entre sí:

1. **Nivel documento (detector de formato):** el 99,7 % de los casos están en PDFs cuyo formato
   se detectó como **`sin_codigo`** → `parsear_linea` entra al ramas de *auto‑detección por línea*.
2. **Nivel línea (regex de código):** en esa rama, los tres patrones que se prueban
   (`GUION`, `PUNTO`, `COMPACTO`) **rechazan** estas líneas por restricciones de forma que no
   coinciden con los códigos reales presentes en ellas.

Ambas causas comparten **una misma restricción de diseño** que se detalla abajo.

---

## 1. Nivel documento: formato detectado

| `formato_codigo` detectado | CODIGOS | % |
|---|--------:|---:|
| `sin_codigo` | 2.748 | **99,7 %** |
| `punto` | 7 | 0,3 % |
| **Total** | **2.755** | 100 % |

> Lectura: en el 99,7 % de los casos el *clasificador de formato del documento* decidió que el
> PDF **no tiene códigos** (`SIN_CODIGO`), por lo que ni siquiera se intenta una extracción a nivel
> de documento con un patrón fijo. El parser queda entonces a merced del auto-detect por línea del
> rama `SIN_CODIGO`.

**Extractor / grupo / OCR de estas líneas:**
- Extractor: `universal` 2.053 (74,5 %) · `nogales` 702 (25,5 %).
- Familia documental: `validacion` 1.212 · `edge_cases` 1.101 · `TRAINING` 258 · `PROCESSING` 157 ·
  `HOLDOUT` 25.
- OCR: texto 2.369 (86 %) · OCR 386 (14 %).

---

## 2. Nivel línea: causa en `parsear_linea` (patrones demasiado estrictos)

`parsear_linea` con `formato SIN_CODIGO` prueba en orden los patrones de `PATRONES_CODIGO_LINEA`
(`parser_universal.py` líneas 414‑418 y 519‑524):

```python
GUION:    ^(\d+(?:-\d+){2,})\s+(.+)     # ⇒ exige 2+ guiones (estructura 1-2-3)
PUNTO:    ^(\d+(?:\.\d+){2,})\s+(.+)     # ⇒ exige 2+ puntos
COMPACTO: ^(\d{5,10})\s+(.+)             # ⇒ exige espacio tras 5-10 dígitos
```

Para que salga `codigo` solo uno de ellos debe matchear. Los códigos reales de estos 24 PDFs
**no cumplen** esas restricciones por dos motivos que mapean estadio a las dos familias principales:

| Patrón del parser | Requiere | Ejemplo delección que **falla** | Motivo |
|---|---|---|---|
| `GUION` `(?:-\d+){2,}` | **2+ guiones** | `1101-51 CAVA O BANCO …` | solo **1** guión |
| `PUNTO` `(?:\.\d+){2,}` | **2+ puntos** | `1101.51 CAVA …` | solo **1** punto |
| `COMPACTO` `^\d{5,10}\s` | **espacio** tras 5-10 dígitos | `10423CTA PTE OTROS…`, `2107G PROVISION…` | código **pegado** a letras, sin espacio |

Así, aunque el token inicial es claramente un código, `codigo` queda `None`. Este es el mecanismo
exacto que produce la etiqueta `CODIGO_PERDIDO`.

---

## 3. Taxonomía raíz de las 2.755 líneas (medido)

Clasificador determinista sobre el token inicial + cuerpo de cada `raw`.

| Código de familia | Descripción | n | % | PDFs | No‑línea OCR | Con monto |
|---|---:|--:|--:|--:|--:|--:|
| **CODIGO‑1SEP** | código legible con **1 partición** (guion/punto único): `1101-51`, `3104-03`, `13216-0000` | **1.431** | **51,9 %** | 13 | 342 | 1.320 (92 %) |
| **CONCATENADO** | código compacto/guion **pegado a letras** sin espacio: `10423CTA`, `2107G`, `705007GOs` | **1.228** | **44,6 %** | 9 | 7 | 1.103 (90 %) |
| **RUT/FOlIO** | **ruido no‑cuenta** (RUT, folio, pág.): `76124950-9`, `705007`, números sueltos | 78 | 2,8 % | 15 | 19 | 2 |
| **DOBLE_COLUMNA** | dos cuentas/columnas en una línea (`1102-08 … 3.602.971.706| 3.602.071.706`) | 16 | 0,6 % | 3 | 16 | 13 |
| **OTRO** | mangle OCR irreconducible (`15295[ 135`) | 2 | 0,1 % | 1 | 2 | 0 |
| | **Total** | **2.755** | 100 % | 34 | 386 | 2.438 |

**Accionable = `CODIGO-1` + `CONCATENADO` = 2.659 (96,5 %).** Ruido del detector = 94 (3,4 %).

---

## 4. Concentración por archivo

**CODIGO-1** (13 PDFs): `ECDS Balance 10-2020` (570) · `Balance Capiro 2017‑2018` (171) ·
`Pre-Balance Chilolac 2024` (165) · `Balance Clasificado JGTc` (150) · `Balance Clasificado RGTc` (132) ·
`col_arquitectos` (79) · `donaciones` (78) · …

**CONCATENADO** (9 PDFs): `Pre Balance Tributario VFCH` (666) · `Pre Balance Tributario CASA` (544) ·
`CPTExportadora` (5) · `CPTGonzagri` (5) …

> Lectura: top‑2 áreas = 1.808 = **66 %**; son los títulos "Pre-Balance Tributario" (formato de 1‑1)
> y "Balance Clasificado". Fix acotado a ≤15 archivos cubre ~96 %.

---

## 5. Impacto esperado por familia

Base: 158.251 cuentas, código 14.134 (**8,93 %**), monto 67.602 (42,72 %).

| Familia | n | Cobertura código (impacto) | Cobertura combinada (código+monto) |
|---|---:|---:|---:|
| CODIGO‑1 | 1.431 | +0,90 pp → | +1.320 monto‑con‑código |
| CONCATENADO | 1.228 | +0,78 pp → | +1.103 monto‑con‑código |
| **Total accionable** | **2.659** | **+1,68 pp** → **10,61 %** | **+2.423** filas pasan a código+monto |
| Ruido (RUT/OTRO) | 94 | no aplica (falsos del detector) | – |

Cobertura código refundando: accionable a **10,61 %** (vs 10,67 % bruto de la priorización, que
contaba los 2.755; al descontar ruido se refina a **2.659**).

---

## 6. Estrategia de corrección sugerida (paro; NO implementado)

Las dos familias principales comparten un mismo origen (patrones de código demasiado estrict) y se
corrigan con el mismo acto: **relajar `PATRONES_CODIGO_LINEA`. Sin cambios al formato a nivel
documento si no se usa.** (Skip — ver riesgos.)

| # | Familia | Fix conceptual | Esfuerzo | Riesgo | Efecto cobertura |
|---|---|---|:--:|:--:|:--:|
| **FG1** | CODIGO‑1 (1.431) | permitir **1 partición** en GUION/PUNTO (`\d{1,6}[-.]\d{1,6}`) en el sincodigo/auto‑ramas | MEDIO | MEDIO‑ALTO | **+0,90 pp** |
| **FG2** | CONCATENADO (1.228) | reconocer prefijo 4‑6 dígitos pegado a abreviatura/letra (partir en dígito→letra) | MEDIO | MEDIO‑ALTO | **+0,78 pp** |
| **FG3** | RUT/FOLLO (78) | reforzar `GARBAGE_PATTERNS`/detector | BAJO | BAJO | higiene del indicador |
| **FG4** | DOBLE_COLUMNA (16) | manejar 2 columnas/`\|` | ALTO | ALTO | ~0 rendimiento |

**Recomendación:** atacar **FG1+FG2 juntos** (misma causa: patron gut). Beneficio medible máximo
(2.659 códigos → cobertura de código 8,93 % → 10,61 %, la métrica más débil) con testable acotado
a 15 PDFs.

---

## 7. Riesgos y salvaguardas

- **Código es ground truth**: a diferencia de nombres, el código es objetivo; si tras el fix el
  código aparece en la fila, el fix funcionó (re‑count verificable sobre benchmark congelado).
- **Riesgo de falsos positivos**: al relajar guion/punto con 1 partición, cuidado con
  RUT/folios/fechas (`76.123…`, paginación) — mitigar restringiendo a cortos (2‑6 dígitos) y
  rango de código PUC/nombre presente.
- **Impacto benchmark**: exposición CODIGO 189 hallazgos/20 archivos; un fix correcto lo mejora →
  re‑congelar solo tras aprobación.
- **No tocar** `extractor_nogales` por separado; el alcance es el mismo núcleo (área protegida).

---

## 8. Conclusión

CODIGO_PERDIDO **no es un ruido**: el **96,5 %** son códigos reales y legibles cuyo formato se
detectó como `sin_codigo` y que `parsear_linea` rechaza por restricciones de forma (guion/punto
exigen 2+ particiones; compacto exige espacio). Corregir **2.659** códigos → cobertura de código
**8,93 % → 10,61 %** (+1,68 pp), la única categoría que actúa sobre la métrica más débil del
proyecto, con mayor efecto en homologación y en el Learning Loop.

> Archivos de referencia del mismo ciclo: `PQ2_PRIORITY_ANALYSIS.md` (por qué es la prioridad),
> `PQ1_SYMBOL_ANALYSIS.md` / `PQ1_SYMBOL_AUDIT.md` (CI de la categoría anterior). Ningún cambio de
> código: medición y auditoría.