# UNKNOWN Root Cause Analysis (URCA)

Generado: 2026-07-10 01:34:12 UTC

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas en pipeline | 10,672 |
| Clasificadas | 1,952 |
| UNKNOWN | 8,720 |
| Cobertura actual | 18.3% |
| Documentos analizados | 185 |

## Distribución de Causas Raíz (Pareto)

| # | Causa Raíz | Cuentas | % | % Acumulado | Monto (USD) |
|---|-----------|---------|----|-------------|-------------|
| 1 | RC05_DICTIONARY | 5,134 | 58.9% | 58.9% | $1,188,609,604,121 |
| 2 | RC06_CMCC | 2,637 | 30.2% | 89.1% | $865,356,739,213 |
| 3 | RC02_OCR | 473 | 5.4% | 94.5% | $98,394,239,447 |
| 4 | RC01_LAYOUT | 292 | 3.3% | 97.9% | $57,225,360,624 |
| 5 | RC04_NORMALIZATION | 184 | 2.1% | 100.0% | $83,585,921,796 |

## Análisis de Pareto

**Top 3 causas: 94.5%** del total de UNKNOWN.
✅ **Las primeras tres causas explican ≥80% del problema.**

## Simulación de Cobertura

| Escenario | Cuentas Recuperadas | Nueva Cobertura | Ganancia |
|-----------|--------------------|-----------------|----------|
| Eliminar RC05_DICTIONARY | 5,134 | 66.4% | +48.1pp |
| Eliminar RC06_CMCC | 2,637 | 43.0% | +24.7pp |
| Eliminar RC02_OCR | 473 | 22.7% | +4.4pp |
| Eliminar RC01_LAYOUT | 292 | 21.0% | +2.7pp |
| Eliminar RC04_NORMALIZATION | 184 | 20.0% | +1.7pp |
| Eliminar top 1 causas (RC05_DICTIONARY) | 5,134 | 66.4% | +48.1pp |
| Eliminar top 2 causas (RC05_DICTIONARY, RC06_CMCC) | 7,771 | 91.1% | +72.8pp |
| Eliminar top 3 causas (RC05_DICTIONARY, RC06_CMCC, RC02_OCR) | 8,244 | 95.5% | +77.2pp |
| Eliminar top 4 causas (RC05_DICTIONARY, RC06_CMCC, RC02_OCR, RC01_LAYOUT) | 8,536 | 98.3% | +80.0pp |
| Eliminar top 5 causas (RC05_DICTIONARY, RC06_CMCC, RC02_OCR, RC01_LAYOUT, RC04_N | 8,720 | 100.0% | +81.7pp |

### Eliminando RC01 (Layout)
**+2.7 pp** de cobertura (292 cuentas recuperadas).

### Eliminando RC05 (Dictionary)
**+48.1 pp** de cobertura (5,134 cuentas recuperadas).

### Eliminando RC06 (CMCC)
**+24.7 pp** de cobertura (2,637 cuentas recuperadas).

## Análisis de Dependencias

| Dependencia | Cuentas | % del UNKNOWN |
|-------------|---------|---------------|
| **Parser** (layout + extracción) | 292 | 3.3% |
| **Conocimiento** (diccionario + CMCC + ambigüedad + reglas) | 7,771 | 89.1% |
| **OCR** (texto ilegible) | 473 | 5.4% |
| **Layout** (estructura) | 292 | 3.3% |

## Detalle por Causa Raíz

### RC05_DICTIONARY

**La cuenta llegó limpia al clasificador pero ninguna variante del diccionario coincide. Problema de conocimiento.**

| Métrica | Valor |
|---------|-------|
| Cuentas afectadas | 5,134 (58.9%) |
| Empresas afectadas | 1 |
| Documentos afectados | 1 |
| Monto acumulado | $1,188,609,604,121 |

### RC06_CMCC

**Existe la variante en CMCC con alta confianza, pero el pipeline no la utiliza. El conocimiento existe pero no se conecta.**

| Métrica | Valor |
|---------|-------|
| Cuentas afectadas | 2,637 (30.2%) |
| Empresas afectadas | 1 |
| Documentos afectados | 1 |
| Monto acumulado | $865,356,739,213 |

### RC02_OCR

**Texto ilegible por OCR. Caracteres rotos, palabras truncadas, ruido de OCR en nombre de cuenta.**

| Métrica | Valor |
|---------|-------|
| Cuentas afectadas | 473 (5.4%) |
| Empresas afectadas | 1 |
| Documentos afectados | 1 |
| Monto acumulado | $98,394,239,447 |

### RC01_LAYOUT

**La cuenta existe pero el parser no identificó la estructura del documento (layout desconocido, columnas desplazadas, tabla partida, header ambiguo).**

| Métrica | Valor |
|---------|-------|
| Cuentas afectadas | 292 (3.3%) |
| Empresas afectadas | 1 |
| Documentos afectados | 1 |
| Monto acumulado | $57,225,360,624 |

### RC04_NORMALIZATION

**La cuenta se extrajo pero la normalización (acentos, mayúsculas, puntuación, plurales) impidió el matching.**

| Métrica | Valor |
|---------|-------|
| Cuentas afectadas | 184 (2.1%) |
| Empresas afectadas | 1 |
| Documentos afectados | 1 |
| Monto acumulado | $83,585,921,796 |
| Fuzzy match candidates | {'Diferencia Cambio en US$', 'Documentos y cuentas por cobrar empresas relacionadas', 'Leyes Sociales por Pagar', 'Documentos y cuentas por pagar empresas relacionadas', '20800IMPUESTOS POR PAGAR', 'a PERDIDA DEL EJERCICIO', 'Pasivos por Impuesto diferido', 'PRESTAMO PERSONAL', 'AL 31 DE DICIEMBRE DE', 'OTROS EGRESOS', 'IMPTO.RENTA', 'Ingresos de explotación', 'Diferencia Tipo de Cambio', 'Provisione de Vacaciones', 'MUTUAL DE SEGURIDAD', '30520CORRECCION MONETARIA', 'Impuesto Unico', ': BANCO CHILE', 'Pérdidas/ Ganancias', 'Al 31 de Diciembre de', '40480IMPUESTO A LA RENTA', '10610ANTICIPO A PROVEEDORES', 'UNURGIA ELECTRICA', 'Deprec. Muebles y Utiles', 'Ingresos de Explotación', 'Intereses por Prestamos Bancar', '20310CTA CTE EMPRES RELACIONADAS', '40460DEUDORES INCOBRABLES', 'CORREC. MONETARIA', 'IMPTO. RENTA POR PAGAR', 'IMPUESTO UNICO', '| ANTICIPO SUELDOS', 'Activos por impuestos diferidos', '20730INSTITUCIONES DE PREVISION', 'CREDITOS BANCARIOS CP', 'CREDITO HIPOTECARIO L/P', '20740REMUNERACIONES POR PAGAR', 'ARRIENDOS PAGADOS POR ANTICIPADO', 'e COMBUSTIBLES', 'al 31 de Diciembre', 'O DIFERENCIA DECAMBIO >', 'PRESTAMOS POR PAGAR', 'PLANTACIÓN', 'CAJA DE COMPENSACION', 'A131 de Diciembre de', '40420COSTO DE VENTA ACTIVO FIJO', '20780HONORARIOS POR PAGAR', 'Provisión Deudas incobrables', '20130PROVEEDORES EXTRANJEROS', 'BANCO CHILE', 'Banco BC!', 'Pérdidas / Ganancias', 'INGRESOS DE EXPLOTACION', 'GASTOS CAPACITACION', 'Impto. Unico al Trabajador', '() Depreciación del Ejercioto e', 'Otros Ingresos por Arriendos', 'Otros Gastos del Personal (I)', 'FONDOS POR RENDIR J.C', 'Gastos Capacitación (I)', '11130I.V.A. CREDITO FISCAL', 'PERDIDAS Y GANANCIAS', 'Plantación', 'CTA.CTE.EMP.RELACIONADAS DALMA', 'INTERESES DIFERIDO USD', 'PRESTAMO C.A', 'Al 31 DE DICIEMBRE', 'Impto. 2a Categoría por Pagar', '10730CTA CTE EMPRES RELACIONADAS', 'CORRECCION MONETARIA DE PASIVO', 'AL 31 DE DICIEMBRE', 'MUEBLES 8: UTILES', 'CREDITO BANCARIOS L', 'ANTICIPO SUELDOS', 'Perdidas por Impuestos Diferidos', '| GTA. CTE SOCIOS', 'Provisión Deudas Incobrables', 'AL31 de Diciembre de', 'UTILIDAD POR DISTRIBUIR', 'CREDITO HIPOTECARIO C/P', 'PERDIDAS Y GANANCIAS —', 'ENERGIA ELECTRICA', 'INGRESOS DE EXPLOTACIÓN', 'Energia Electrica', 'OTROS GASTOS DE', 'I.V.A. RETENIDO A TERCEROS', 'PASIVOS EN LEASING', '40% Impto. Unico', 'Ingresos Varios', 'INTERESES BANCO', 'Banco Chile'} |

## Respuestas a Preguntas Clave

### 1. ¿Qué porcentaje de UNKNOWN pertenece a cada causa?

- **RC05_DICTIONARY**: 58.9% (5,134 cuentas)
- **RC06_CMCC**: 30.2% (2,637 cuentas)
- **RC02_OCR**: 5.4% (473 cuentas)
- **RC01_LAYOUT**: 3.3% (292 cuentas)
- **RC04_NORMALIZATION**: 2.1% (184 cuentas)

### 2. ¿Las primeras tres causas explican el 80%?

**Sí.** Las primeras tres causas representan **94.5%** del total.

### 3. ¿Cuánto mejoraría la cobertura eliminando RC01 (Layout)?
**+2.7 pp** (de 18.3% a 21.0%).

### 4. ¿Cuánto mejoraría eliminando RC05 (Dictionary)?
**+48.1 pp** (de 18.3% a 66.4%).

### 5. ¿Cuánto depende realmente del parser?
**3.3%** del UNKNOWN (292 cuentas).

### 6. ¿Cuánto depende del conocimiento (diccionario + CMCC)?
**89.1%** del UNKNOWN (7,771 cuentas).

### 7. ¿Cuánto depende del OCR?
**5.4%** del UNKNOWN (473 cuentas).

### 8. ¿Cuánto depende del layout?
**3.3%** del UNKNOWN (292 cuentas).

## Orden por ROI Esperado

Priorizado por: esfuerzo × impacto × cantidad de cuentas afectadas.

| ROI | Causa | Cuentas | Esfuerzo | Estrategia |
|-----|-------|---------|----------|------------|
| 1 (Máximo) | RC04_NORMALIZATION | 184 | Bajo | Implementar normalize + fuzzy match |
| 2 (Alto) | RC06_CMCC | 2,637 | Bajo-Medio | Integrar CMCC al pipeline clasificador |
| 3 (Alto) | RC01_LAYOUT | 292 | Bajo | Filtrar artefactos (fechas, encabezados) |
| 4 (Medio) | RC05_DICTIONARY (abreviaturas) | 422 | Medio | Expandir abreviaturas antes del matching |
| 5 (Medio) | RC02_OCR | 473 | Medio-Alto | Mejorar OCR / limpiar ruido post-extracción |
| 6 (Bajo) | RC05_DICTIONARY (nuevas cuentas) | 3,127 | Alto | Población masiva de diccionario |

## ¿Cuál es el Verdadero Cuello de Botella?

**El cuello de botella principal es RC05_DICTIONARY**, que representa **58.9%** del total de UNKNOWN.

Sin embargo, el **verdadero cuello de botella del sistema** es:

### 🔴 CONOCIMIENTO (RC05_DICTIONARY)

**5,134 cuentas (58.9%)** no se clasifican porque el diccionario no contiene las variantes necesarias.

La mayoría de estas cuentas son nombres de cuenta válidos que simplemente no existen en el diccionario o existen en forma diferente (abreviaturas, variaciones ortográficas).

---

*Generado por FASE 25B — UNKNOWN Root Cause Analysis (URCA)*