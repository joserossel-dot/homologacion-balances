# CMCC Population Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Conceptos creados | 52 |
| Total variantes | 3064 |
| Total sinónimos | 18 |
| Total ejemplos | 3082 |
| Promedio variantes/concepto | 58.92 |
| Cobertura potencial | 92.3% |
| Fuentes utilizadas | catalogo_maestro.json, diccionario.json, generated_dictionary_entries.json |

## 1. ¿Cuántos conceptos quedaron?

**52 conceptos** fueron creados desde `catalogo_maestro.json`.

## 2. ¿Cuántas variantes?

- **3064 variantes** desde `diccionario.json`
- **18 sinónimos**
- **3082 ejemplos**

## 3. Promedio de variantes por concepto

**58.92 variantes por concepto** en promedio.

## 4. Top 20 conceptos con más variantes

| # | Código | Nombre | Variantes | Sinónimos | Frecuencia |
|---|--------|--------|-----------|-----------|-----------|
| 1 | AC.01 | Caja y Bancos | 1105 | 0 | 1601 |
| 2 | ER.01 | Ventas | 644 | 1 | 49 |
| 3 | ER.02 | Costo de Ventas | 501 | 0 | 116 |
| 4 | ER.04 | Gastos de Administración | 89 | 1 | 0 |
| 5 | PC.01 | Proveedores | 74 | 1 | 111 |
| 6 | ANC.01 | Activo Fijo | 62 | 0 | 0 |
| 7 | AC.07 | Otras Cuentas por Cobrar CP | 53 | 0 | 0 |
| 8 | PAT.01 | Capital | 45 | 1 | 114 |
| 9 | PC.06 | Remuneraciones por Pagar | 37 | 1 | 0 |
| 10 | PC.08 | Otros Pasivos Corrientes | 35 | 0 | 0 |
| 11 | PC.05 | Impuestos por Pagar | 34 | 1 | 0 |
| 12 | AC.05 | Inventarios | 33 | 0 | 0 |
| 13 | PC.02 | Obligaciones Bancarias CP | 28 | 0 | 0 |
| 14 | ER.09 | Gastos Financieros | 24 | 1 | 0 |
| 15 | ANC.06 | Otros Activos No Corrientes | 24 | 0 | 0 |
| 16 | AC.03 | Clientes | 24 | 1 | 0 |
| 17 | ER.13 | Otras Ganancias y Pérdidas | 18 | 3 | 0 |
| 18 | PAT.02 | Reservas | 16 | 0 | 0 |
| 19 | AC.06S | Cta. Cte. Socios / Retiros (Activo) | 15 | 0 | 0 |
| 20 | AC.06 | Relacionadas CP | 15 | 0 | 0 |

## 5. Top 20 conceptos más frecuentes

| # | Código | Nombre | Frecuencia | Variantes | Empresas |
|---|--------|--------|-----------|-----------|----------|
| 1 | AC.01 | Caja y Bancos | 1601 | 1105 | 0 |
| 2 | ER.02 | Costo de Ventas | 116 | 501 | 0 |
| 3 | PAT.01 | Capital | 114 | 45 | 0 |
| 4 | PC.01 | Proveedores | 111 | 74 | 0 |
| 5 | ER.01 | Ventas | 49 | 644 | 0 |
| 6 | AC.04 | Documentos por Cobrar | 0 | 11 | 0 |
| 7 | AC.06S | Cta. Cte. Socios / Retiros (Activo) | 0 | 15 | 0 |
| 8 | AC.06 | Relacionadas CP | 0 | 15 | 0 |
| 9 | AC.08 | Otros Activos Corrientes | 0 | 6 | 0 |
| 10 | AC.05 | Inventarios | 0 | 33 | 0 |
| 11 | ANC.02 | Propiedades de Inversión | 0 | 0 | 0 |
| 12 | AC.07 | Otras Cuentas por Cobrar CP | 0 | 53 | 0 |
| 13 | ANC.03 | Intangibles | 0 | 12 | 0 |
| 14 | ANC.04 | Inversiones Permanentes | 0 | 6 | 0 |
| 15 | ANC.05 | Relacionadas LP | 0 | 9 | 0 |
| 16 | ANC.06 | Otros Activos No Corrientes | 0 | 24 | 0 |
| 17 | PC.02 | Obligaciones Bancarias CP | 0 | 28 | 0 |
| 18 | ANC.01 | Activo Fijo | 0 | 62 | 0 |
| 19 | AC.03 | Clientes | 0 | 24 | 0 |
| 20 | AC.02 | Inversiones Corto Plazo | 0 | 10 | 0 |

## 6. Top conceptos con problemas

### Conceptos sin variantes (4)
- ANC.02: Propiedades de Inversión
- ER.03: Margen Bruto
- ER.06: EBITDA
- ER.08: Resultado Operacional

### Conceptos con confianza baja (0)

## 7. Duplicados detectados

### Conflictos por normalización (11)
- Normalizada: "bonos" → AC.01 | PNC.03
- Normalizada: "documentos cobrar" → AC.01 | AC.04
- Normalizada: "otros activo corrientes" → AC.01 | AC.08
- Normalizada: "inventarios" → AC.05 | ER.01
- Normalizada: "relacionada cp" → AC.06 | PC.07
- Normalizada: "intangible" → ANC.03 | ER.01
- Normalizada: "relacionada lp" → ANC.05 | PNC.04
- Normalizada: "factoring" → ER.02 | PC.04
- Normalizada: "reservas" → ER.02 | PAT.02
- Normalizada: "ebitda" → ER.01 | ER.06
- Normalizada: "diferencia cambio" → ER.09 | ER.15

### Variantes duplicadas entre conceptos (0)

### Sinónimos candidatos (20)
- "AC.06: Relacionadas CP" ↔ "PC.07: Relacionadas CP" (similitud: 100.0%)
- "ANC.05: Relacionadas LP" ↔ "PNC.04: Relacionadas LP" (similitud: 100.0%)
- "PC.02: Obligaciones Bancarias CP" ↔ "PNC.01: Obligaciones Bancarias LP" (similitud: 95.65217391304348%)
- "AC.09: Activos Biológicos CP" ↔ "ANC.07: Activos Biológicos LP" (similitud: 95.0%)
- "AC.08: Otros Activos Corrientes" ↔ "ANC.06: Otros Activos No Corrientes" (similitud: 93.87755102040816%)
- "AC.06: Relacionadas CP" ↔ "ANC.05: Relacionadas LP" (similitud: 92.85714285714286%)
- "AC.06: Relacionadas CP" ↔ "PNC.04: Relacionadas LP" (similitud: 92.85714285714286%)
- "ANC.05: Relacionadas LP" ↔ "PC.07: Relacionadas CP" (similitud: 92.85714285714286%)
- "PC.07: Relacionadas CP" ↔ "PNC.04: Relacionadas LP" (similitud: 92.85714285714286%)
- "PC.03: Leasing CP" ↔ "PNC.02: Leasing LP" (similitud: 90.0%)
- "AC.08: Otros Activos Corrientes" ↔ "PC.08: Otros Pasivos Corrientes" (similitud: 89.36170212765957%)
- "ER.09: Gastos Financieros" ↔ "ER.12: Ingresos Financieros" (similitud: 84.21052631578947%)
- "ANC.06: Otros Activos No Corrientes" ↔ "PC.08: Otros Pasivos Corrientes" (similitud: 84.0%)
- "PAT.03: Utilidades Retenidas" ↔ "ER.11: Utilidad Neta" (similitud: 75.0%)
- "PAT.04: Resultado del Ejercicio" ↔ "ER.08: Resultado Operacional" (similitud: 75.0%)
  ... y 5 más

## 8. Conceptos sin código

**0 conceptos sin código** — todos los conceptos tienen código estándar.

## 9. Conceptos ambiguos

Los 11 conflictos de normalización indican posibles ambigüedades
donde una misma variante normalizada aparece en múltiples conceptos.

## 10. Distribución por tipo de estado financiero

| Tipo | Conceptos |
|------|-----------|
| balance | 36 |
| resultado | 16 |

## 11. Distribución por categoría

| Categoría | Conceptos |
|-----------|-----------|
| activo_corriente | 10 |
| activo_no_corriente | 8 |
| pasivo_corriente | 8 |
| pasivo_no_corriente | 5 |
| patrimonio | 5 |
| resultado | 16 |

## 12. Validación

| Validación | Resultado |
|-----------|-----------|
| Dos concepts con mismo código | OK |
| Variante en dos concepts | OK |
| Conceptos sin código | OK (0) |
| Variantes totales | 3064 |
| Total guardado en cmcc.json | 52 conceptos |

## 13. Próximos pasos

1. Revisar 11 conflictos de normalización
2. Resolver 0 variantes en múltiples conceptos
3. Evaluar 20 candidatos a sinónimo
4. Poblar 4 conceptos sin variantes
5. Integrar CMCC con el pipeline clasificador
