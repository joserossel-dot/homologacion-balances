# Pareto Recovery Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas sin clasificar | 5,992 |
| Mejoras evaluadas | 435 |
| Mejoras con beneficio neto (no solapado) | 34 |
| Cobertura final (sin solapamiento) | 100.0% |
| Cuentas recuperables únicas | 5,992 |

## 1. ¿Cuáles son las 20 mejoras que más cobertura recuperan?

| # | ID | Tipo | Descripción | Cuentas nuevas | Esfuerzo | ROI |
|---|-----|------|-------------|---------------|----------|-----|
| 1 | DICT-NEW | Diccionario | Agregar nuevas cuentas al diccionario con código estándar | 4998 | 5 | 1456.2 |
| 2 | NORM-FUZZY | Normalización | Implementar normalización (tildes, mayúsculas, puntuación) + fuzz | 91 | 1 | 214.0 |
| 3 | ABB-cta | Abreviatura | Expandir "cta" → "cuenta" | 144 | 1 | 211.0 |
| 4 | PAT-Gastos | Regla | Regla: cuentas que contienen "Gastos" → asignar código estándar | 21 | 3 | 7.3 |
| 5 | OCR-NOISE | OCR | Filtrar/limpiar cuentas con ruido de OCR | 454 | 4 | 129.0 |
| 6 | PARSER-ART | Parser | Filtrar artefactos del parser (fechas, encabezados, páginas) | 43 | 2 | 71.5 |
| 7 | ABB-dep | Abreviatura | Expandir "dep" → "depósito" | 49 | 1 | 78.0 |
| 8 | PAT-Cuentas | Regla | Regla: cuentas que contienen "Cuentas" → asignar código estándar | 3 | 3 | 1.0 |
| 9 | PAT-Banco | Regla | Regla: cuentas que contienen "Banco" → asignar código estándar | 2 | 3 | 0.7 |
| 10 | PAT-Capital | Regla | Regla: cuentas que contienen "Capital" → asignar código estándar | 13 | 3 | 5.3 |
| 11 | ABB-mat | Abreviatura | Expandir "mat" → "materiales" | 36 | 1 | 44.0 |
| 12 | PAT-Venta | Regla | Regla: cuentas que contienen "Venta" → asignar código estándar | 3 | 3 | 2.0 |
| 13 | ABB-rev | Abreviatura | Expandir "rev" → "revisión" | 8 | 1 | 13.0 |
| 14 | ABB-inv | Abreviatura | Expandir "inv" → "inventario" | 20 | 1 | 28.0 |
| 15 | ABB-soc | Abreviatura | Expandir "soc" → "sociedad" | 22 | 1 | 29.0 |
| 16 | PAT-Ingresos | Regla | Regla: cuentas que contienen "Ingresos" → asignar código estándar | 1 | 3 | 0.3 |
| 17 | ABB-ctas | Abreviatura | Expandir "ctas" → "cuentas" | 21 | 1 | 28.0 |
| 18 | ABB-vta | Abreviatura | Expandir "vta" → "venta" | 6 | 1 | 12.0 |
| 19 | ABB-fdo | Abreviatura | Expandir "fdo" → "fondo" | 7 | 1 | 7.0 |
| 20 | ABB-adm | Abreviatura | Expandir "adm" → "administración" | 6 | 1 | 8.0 |

## 2. ¿Cuántas cuentas recupera cada una de las top 20?

- **1. DICT-NEW** (Diccionario): Agregar nuevas cuentas al diccionario con código estándar → **4998 cuentas**, esfuerzo 5, ROI 1456.2
- **2. NORM-FUZZY** (Normalización): Implementar normalización (tildes, mayúsculas, puntuación) + → **91 cuentas**, esfuerzo 1, ROI 214.0
- **3. ABB-cta** (Abreviatura): Expandir "cta" → "cuenta" → **144 cuentas**, esfuerzo 1, ROI 211.0
- **4. PAT-Gastos** (Regla): Regla: cuentas que contienen "Gastos" → asignar código están → **21 cuentas**, esfuerzo 3, ROI 7.3
- **5. OCR-NOISE** (OCR): Filtrar/limpiar cuentas con ruido de OCR → **454 cuentas**, esfuerzo 4, ROI 129.0
- **6. PARSER-ART** (Parser): Filtrar artefactos del parser (fechas, encabezados, páginas) → **43 cuentas**, esfuerzo 2, ROI 71.5
- **7. ABB-dep** (Abreviatura): Expandir "dep" → "depósito" → **49 cuentas**, esfuerzo 1, ROI 78.0
- **8. PAT-Cuentas** (Regla): Regla: cuentas que contienen "Cuentas" → asignar código está → **3 cuentas**, esfuerzo 3, ROI 1.0
- **9. PAT-Banco** (Regla): Regla: cuentas que contienen "Banco" → asignar código estánd → **2 cuentas**, esfuerzo 3, ROI 0.7
- **10. PAT-Capital** (Regla): Regla: cuentas que contienen "Capital" → asignar código está → **13 cuentas**, esfuerzo 3, ROI 5.3
- **11. ABB-mat** (Abreviatura): Expandir "mat" → "materiales" → **36 cuentas**, esfuerzo 1, ROI 44.0
- **12. PAT-Venta** (Regla): Regla: cuentas que contienen "Venta" → asignar código estánd → **3 cuentas**, esfuerzo 3, ROI 2.0
- **13. ABB-rev** (Abreviatura): Expandir "rev" → "revisión" → **8 cuentas**, esfuerzo 1, ROI 13.0
- **14. ABB-inv** (Abreviatura): Expandir "inv" → "inventario" → **20 cuentas**, esfuerzo 1, ROI 28.0
- **15. ABB-soc** (Abreviatura): Expandir "soc" → "sociedad" → **22 cuentas**, esfuerzo 1, ROI 29.0
- **16. PAT-Ingresos** (Regla): Regla: cuentas que contienen "Ingresos" → asignar código est → **1 cuentas**, esfuerzo 3, ROI 0.3
- **17. ABB-ctas** (Abreviatura): Expandir "ctas" → "cuentas" → **21 cuentas**, esfuerzo 1, ROI 28.0
- **18. ABB-vta** (Abreviatura): Expandir "vta" → "venta" → **6 cuentas**, esfuerzo 1, ROI 12.0
- **19. ABB-fdo** (Abreviatura): Expandir "fdo" → "fondo" → **7 cuentas**, esfuerzo 1, ROI 7.0
- **20. ABB-adm** (Abreviatura): Expandir "adm" → "administración" → **6 cuentas**, esfuerzo 1, ROI 8.0

## 3. Cobertura acumulada después de implementar

| Hito | Cuentas acumuladas | Cobertura | Incremento marginal |
|------|-------------------|-----------|-------------------|
| Top 1.0 | 4998.0 | 83.4% | +83.4% |
| Top 5.0 | 5708.0 | 95.3% | +11.9% |
| Top 10.0 | 5818.0 | 97.1% | +1.8% |
| Top 20.0 | 5948.0 | 99.3% | +2.2% |
| Top 30.0 | 5988.0 | 99.9% | +0.6% |

**Cobertura total final**: 100.0%

## 4. ¿Qué porcentaje del beneficio proviene de las primeras 20?

- Beneficio total alcanzable: **100.0%** (5,992 cuentas)
- Beneficio solo con top 20: **99.3%** (5,948 cuentas)
- Las primeras 20 representan **99.3%** del beneficio total

## 5. ¿Cuáles requieren contador?

| ID | Tipo | Descripción |
|----|------|-------------|
| DICT-NEW | Diccionario | Agregar nuevas cuentas al diccionario con código estándar |
| PAT-Gastos | Regla | Regla: cuentas que contienen "Gastos" → asignar código están |
| PAT-Cuentas | Regla | Regla: cuentas que contienen "Cuentas" → asignar código está |
| PAT-Banco | Regla | Regla: cuentas que contienen "Banco" → asignar código estánd |
| PAT-Capital | Regla | Regla: cuentas que contienen "Capital" → asignar código está |
| PAT-Venta | Regla | Regla: cuentas que contienen "Venta" → asignar código estánd |
| PAT-Ingresos | Regla | Regla: cuentas que contienen "Ingresos" → asignar código est |

**Total manual (requiere contador)**: 5,495 cuentas (91.7%)

## 6. ¿Cuáles pueden automatizarse sin intervención humana?

| ID | Tipo | Descripción |
|----|------|-------------|
| NORM-FUZZY | Normalización | Implementar normalización (tildes, mayúsculas, puntuación) + |
| ABB-cta | Abreviatura | Expandir "cta" → "cuenta" |
| PARSER-ART | Parser | Filtrar artefactos del parser (fechas, encabezados, páginas) |
| ABB-dep | Abreviatura | Expandir "dep" → "depósito" |
| ABB-mat | Abreviatura | Expandir "mat" → "materiales" |
| ABB-rev | Abreviatura | Expandir "rev" → "revisión" |
| ABB-inv | Abreviatura | Expandir "inv" → "inventario" |
| ABB-soc | Abreviatura | Expandir "soc" → "sociedad" |
| ABB-ctas | Abreviatura | Expandir "ctas" → "cuentas" |
| ABB-vta | Abreviatura | Expandir "vta" → "venta" |
| ABB-fdo | Abreviatura | Expandir "fdo" → "fondo" |
| ABB-adm | Abreviatura | Expandir "adm" → "administración" |
| ABB-prov | Abreviatura | Expandir "prov" → "provisión" |
| ABB-dif | Abreviatura | Expandir "dif" → "diferencia" |
| ABB-rem | Abreviatura | Expandir "rem" → "remuneración" |
| ABB-util | Abreviatura | Expandir "util" → "utilidad" |
| ABB-eq | Abreviatura | Expandir "eq" → "equipo" |
| ABB-merc | Abreviatura | Expandir "merc" → "mercaderías" |
| ABB-depr | Abreviatura | Expandir "depr" → "depreciación" |
| ABB-dcto | Abreviatura | Expandir "dcto" → "descuento" |
| ABB-doc | Abreviatura | Expandir "doc" → "documento" |
| ABB-cap | Abreviatura | Expandir "cap" → "capital" |
| ABB-imp | Abreviatura | Expandir "imp" → "impuesto" |
| ABB-rrhh | Abreviatura | Expandir "rrhh" → "recursos humanos" |
| ABB-pto | Abreviatura | Expandir "pto" → "puesto" |
| ABB-rec | Abreviatura | Expandir "rec" → "recursos" |

**Total automático (sin contador)**: 497 cuentas (8.3%)

## 7. Distribución por tipo de mejora

| Tipo | Mejoras | Cuentas únicas | % del total |
|------|---------|---------------|------------|
| Normalización | 1 | 91 | 1.5% |
| Abreviatura | 24 | 363 | 6.1% |
| Regla | 6 | 43 | 0.7% |
| Diccionario | 1 | 4998 | 83.4% |
| OCR | 1 | 454 | 7.6% |
| Parser | 1 | 43 | 0.7% |

## 8. Orden de implementación recomendado (top 10)

| # | ID | Tipo | Descripción | Cuentas | Esfuerzo |
|---|-----|------|-------------|---------|----------|
| 1 | DICT-NEW | Diccionario | Agregar nuevas cuentas al diccionario con código estánd | 4998 | 5 |
| 2 | NORM-FUZZY | Normalización | Implementar normalización (tildes, mayúsculas, puntuaci | 91 | 1 |
| 3 | ABB-cta | Abreviatura | Expandir "cta" → "cuenta" | 144 | 1 |
| 4 | PAT-Gastos | Regla | Regla: cuentas que contienen "Gastos" → asignar código  | 21 | 3 |
| 5 | OCR-NOISE | OCR | Filtrar/limpiar cuentas con ruido de OCR | 454 | 4 |
| 6 | PARSER-ART | Parser | Filtrar artefactos del parser (fechas, encabezados, pág | 43 | 2 |
| 7 | ABB-dep | Abreviatura | Expandir "dep" → "depósito" | 49 | 1 |
| 8 | PAT-Cuentas | Regla | Regla: cuentas que contienen "Cuentas" → asignar código | 3 | 3 |
| 9 | PAT-Banco | Regla | Regla: cuentas que contienen "Banco" → asignar código e | 2 | 3 |
| 10 | PAT-Capital | Regla | Regla: cuentas que contienen "Capital" → asignar código | 13 | 3 |

## 9. Conclusión

**Ley de Pareto aplicada a la clasificación de cuentas**:

- **4.6%** de las mejoras (top 20) recuperan **99.3%** de las cuentas recuperables
- Las primeras **5 mejoras** recuperan **95.3%** del total (95.3% del beneficio)
- Las primeras **10 mejoras** recuperan **97.1%** del total (97.1% del beneficio)

**Estrategia óptima**:

1. **Sprint inmediato**: Normalización + Fuzzy matching (esfuerzo 1, 0 dependencias)
2. **Sprint 1**: Expandir abreviaturas de alto impacto (cta, dep, mat, rev, inv - esfuerzo 1 c/u)
3. **Sprint 2**: Reglas por patrón (Gastos*, Banco*, Cuentas*, Venta* - requieren código contable)
4. **Sprint 3**: Sinónimos + abreviaturas restantes + filtro parser
5. **Sprint 4**: Diccionario masivo + limpieza OCR

**Impacto esperado**:
- Automático (sin contador): 497 cuentas (8.3%)
- Requiere contador: 5,495 cuentas (91.7%)
- **Total**: 5,992 cuentas (100.0%)
