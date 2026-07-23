# Recovery Opportunity Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas sin clasificar | 5,992 |
| Total registros sin clasificar | 8,720 |
| Oportunidades de mejora identificadas | 435 |
| Cobertura potencial (suma simple) | 139.6% |
| Cobertura potencial (única estimada) | ~5,992 cuentas |

## 1. ¿Cuáles son las 20 mejoras con mayor retorno?

| # | Grupo | Tipo | Cuentas | Ocurrencias | Esfuerzo | ROI |
|---|-------|------|---------|------------|----------|-----|
| 1 | DICT-NEW | Diccionario | 4998 | 7281 | 5 | 1456.2 |
| 2 | ABB-cta | Abreviatura | 144 | 211 | 1 | 211.0 |
| 3 | PAT-Gastos * | Regla | 345 | 486 | 3 | 162.0 |
| 4 | NORM-FUZZY | Normalización | 91 | 214 | 1 | 214.0 |
| 5 | OCR-NOISE | OCR | 466 | 529 | 4 | 132.2 |
| 6 | ABB-dep | Abreviatura | 49 | 78 | 1 | 78.0 |
| 7 | PAT-Banco * | Regla | 145 | 225 | 3 | 75.0 |
| 8 | PAT-Cuentas * | Regla | 119 | 227 | 3 | 75.7 |
| 9 | PAT-Venta * | Regla | 90 | 133 | 3 | 44.3 |
| 10 | ABB-mat | Abreviatura | 37 | 45 | 1 | 45.0 |
| 11 | PAT-Capital * | Regla | 74 | 118 | 3 | 39.3 |
| 12 | ABB-soc | Abreviatura | 29 | 36 | 1 | 36.0 |
| 13 | ABB-inv | Abreviatura | 26 | 37 | 1 | 37.0 |
| 14 | ABB-rev | Abreviatura | 25 | 39 | 1 | 39.0 |
| 15 | ABB-ctas | Abreviatura | 22 | 29 | 1 | 29.0 |
| 16 | PAT-Ingresos * | Regla | 50 | 98 | 3 | 32.7 |
| 17 | PAT-Caja * | Regla | 48 | 86 | 3 | 28.7 |
| 18 | PAT-Impuesto * | Regla | 46 | 67 | 3 | 22.3 |
| 19 | PARSER-ART | Parser | 43 | 143 | 2 | 71.5 |
| 20 | PAT-Activo * | Regla | 43 | 58 | 3 | 19.3 |

## 2. ¿Cuánto aumentaría la cobertura si solo se implementan las top 20?

- Cuentas recuperables: **6,890**
- Ocurrencias recuperables: **10,140**
- Cobertura sobre cuentas totales: **115.0%**
- Cobertura sobre ocurrencias totales: **116.3%**

## 3. ¿Cuánto si se implementan las primeras 50?

- Cuentas recuperables: **7,433**
- Ocurrencias recuperables: **10,936**
- Cobertura sobre cuentas totales: **124.0%**
- Cobertura sobre ocurrencias totales: **125.4%**

## 4. ¿Cuánto si se implementan todas?

- Cuentas recuperables: **8,367**
- Ocurrencias recuperables: **12,758**
- Cobertura sobre cuentas totales: **139.6%**
- Cobertura sobre ocurrencias totales: **146.3%**

Nota: Las cuentas pueden contarse en múltiples categorías. La cobertura real única es menor.

## 5. ¿Qué porcentaje requiere intervención humana?

| Categoría | Cuentas | % del total | Intervención |
|-----------|---------|------------|-------------|
| Nuevas entradas en diccionario | 4,998 | 83.4% | Manual — contador asigna código |
| Abreviaturas con ambigüedad | ~3 | ~0.05% | Revisión de expansión correcta |
| Patrones sin código asignado | 30 | 0.50% | Contador define regla de asignación |

**Total con intervención humana**: ~5028 cuentas (83.9%)

**Sin intervención humana** (automático): ~3339 cuentas (55.7%)

## 6. ¿Cuánto trabajo corresponde realmente al parser?

| Componente | Cuentas | % del total | Esfuerzo estimado |
|-----------|---------|------------|------------------|
| Artefactos del parser (filtrar) | 43 | 0.7% | Bajo (días) |
| Ruido de OCR (limpiar) | 466 | 7.8% | Medio-Alto (depende fuente) |
| Total atribuible al parser/OCR | 509 | 8.5% | — |

## 7. ¿Cuánto corresponde al conocimiento contable?

| Componente | Cuentas | % del total | Descripción |
|-----------|---------|------------|-------------|
| Nuevas entradas en diccionario | 4,998 | 83.4% | Cuentas válidas no mapeadas a código estándar |
| Reglas por patrón | 30 | 0.50% | Requiere definir qué código asignar a cada patrón |
| Normalización (automático contable) | 91 | 1.5% | Ya existen en diccionario, solo normalizar |
| Sinónimos (automático contable) | 934 | 15.6% | Variantes de cuentas ya conocidas |

**Total atribuible al conocimiento contable**: ~5028 cuentas (83.9%) requieren criterio contable.

## 8. Sprint Plan

| Sprint | Items | Esfuerzo | Cuentas | Cobertura individual | Cobertura acumulada | Tipos principales |
|--------|-------|----------|---------|---------------------|-------------------|-------------------|
| Sprint 1 | 99 | 207 | 2141 | 35.7% | 35.7% | Sinónimo | Regla | Abreviatura |
| Sprint 2 | 111 | 221 | 281 | 4.7% | 40.4% | Sinónimo | Abreviatura |
| Sprint 3 | 112 | 222 | 263 | 4.4% | 44.8% | Sinónimo | Abreviatura | Parser |
| Sprint 4 | 113 | 229 | 5682 | 94.8% | 139.6% | Sinónimo | Abreviatura | Regla |

### Sprint 1 — Quick Wins (Alta prioridad)
- Normalización + Fuzzy Matching
- Abreviaturas de alto impacto (cta, dep, mat, rev, inv, soc, ctas)
- Principales sinónimos

### Sprint 2 — Reglas y Abreviaturas
- Patrones de alto impacto (Gastos *, Banco *, Capital *, Ventas *)
- Abreviaturas restantes
- Sinónimos adicionales

### Sprint 3 — Patrones restantes y Parser
- Patrones de menor impacto
- Filtrar artefactos del parser
- Sinónimos restantes

### Sprint 4 — Diccionario y OCR
- Nuevas entradas en diccionario (revisión manual)
- Limpieza de ruido OCR

## 9. Conclusión

**Mayor retorno inmediato**: Normalización + Fuzzy matching (esfuerzo 1, recupera 91 cuentas).

**Mayor impacto absoluto**: Nuevas entradas en diccionario (4998 cuentas, 83.4%) pero requiere revisión manual.

**Porcentaje automático sin intervención humana**: ~1564 cuentas.

**Porcentaje que requiere contador**: ~83.4% (diccionario) + 0.50% (reglas).

**Estrategia recomendada**:
1. Sprint 1: Implementar normalización + fuzzy matching + abreviaturas (días, cero intervención humana)
2. Sprint 2: Agregar reglas por patrón con revisión contable ligera
3. Sprint 3: Limpiar artefactos del parser y sinónimos restantes
4. Sprint 4: Abordar diccionario nuevo con revisión manual masiva + mejora OCR
