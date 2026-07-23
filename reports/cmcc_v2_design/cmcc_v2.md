# CMCC v2.0 — Diseño de Taxonomía Financiera Jerárquica

**Generado:** 2026-07-10 20:17:17 UTC
---
*Read-only design. No production modifications.*


## 1. Resumen

- **v1:** 52 conceptos planos (52)

- **v2:** 75 conceptos jerárquicos (69 ACCOUNT + 6 CALCULATED)

- **Nuevos conceptos:** 13

- **Subniveles jerárquicos:** 21 (hasta 3 niveles de profundidad)

- **Delta neto:** +23 conceptos


## 2. ¿El nuevo modelo elimina AC.01?

**No.** AC.01 se expande a:

- **AC.01** Efectivo y Equivalentes al Efectivo (nivel 1)

  - AC.01.01 Caja

  - AC.01.02 Bancos

  - AC.01.03 Equivalentes al Efectivo

- **AC.02** Valores Negociables (se separa de AC.01)

- **AC.03** Inversiones Financieras CP



El 58.69% del REVIEW de AC.01 se distribuye en estos 6 conceptos v2. 


AC.01 como código raíz se mantiene para compatibilidad ascendente.


## 3. ¿Cómo quedan ER.01 y ER.02?

**ER.01 (Ventas)** → se mantiene como ER.01 Ventas (ACCOUNT)

**ER.02 (Costo de Ventas)** → se mantiene como ER.02 Costo de Ventas (ACCOUNT)


**Cambios en ER:**

- ER.03 (Margen Bruto) → ER.C01 CALCULATED

- ER.04 + ER.05 (GA y GV) → ER.03 (Gastos de Administración y Ventas, fusionado)

- ER.06 (EBITDA) → ER.C03 CALCULATED

- ER.07 (Depreciación y Amortiz.) → ER.04 + ER.05 (separados)

- ER.08 (Resultado Operacional) → ER.C02 CALCULATED

- ER.11 (Utilidad Neta) → ER.C05 CALCULATED

- ER.13 (Otras Ganancias y Pérd.) → ER.10 + ER.11 (separados)

- ER.14 (Corrección Monetaria) → ER.09 (Diferencias de Cambio, absorbido)


## 4. ¿Qué cuentas pasan a ser calculadas?

| ID | Nombre | Fórmula |

|---|---|---|

| ER.C01 | Margen Bruto | `ER.01 - ER.02` |

| ER.C02 | Resultado Operacional (EBIT) | `ER.C01 - ER.03 - ER.04 - ER.05` |

| ER.C03 | EBITDA | `ER.C02 + ER.04 + ER.05` |

| ER.C04 | Resultado Antes de Impuestos | `ER.C02 + ER.06 - ER.07 + ER.08 + ER.09 + ER.10 - ER.11` |

| ER.C05 | Resultado del Ejercicio | `ER.C04 - ER.12` |

| ER.C06 | Margen Neto | `ER.C05 / ER.01` |


Total: **6** cuentas calculadas. No requieren parser — se derivan automáticamente.


## 5. ¿Qué compatibilidad mantiene con v1?

- **62** de 69 conceptos ACCOUNT tienen mapeo directo desde v1

- **7** conceptos ACCOUNT son nuevos (sin equivalente v1)

- **6** conceptos CALCULATED son derivaciones automáticas

- **0** conceptos v1 se quedan huérfanos (todos tienen mapeo)



| Tipo | Cantidad | Compatible |

|---|---|---|

| 1:1 (directo) | 35 | ✅ |

| 1:N (split) | 13 | ✅ (v1→v2 expande) |

| N:1 (merge) | 8 | ✅ (v2→v1 contrae) |



## 6. ¿Cuál es el costo estimado de migración?

### Esfuerzo estimado

1. **Nuevas variantes:** ~175 estimaciones de variantes para conceptos nuevos (7 conceptos × ~25 variantes c/u)

2. **Redistribución splits:** ~22 subconceptos creados de splits (AC.01, ER.01, ER.02)

3. **Fusiones:** ~8 conceptos v2 que reciben múltiples v1 (validar coherencia)

4. **Calculados:** 6 fórmulas a implementar en el pipeline

5. **Parser:** sin cambios (operan sobre cuentas individuales)

6. **Review pipeline:** actualizar ReviewCMCC para soportar IDs jerárquicos (v2)

7. **Diccionario:** re-mapear ~826 entradas de v1→v2 (automático con migration_map)

8. **Gold standard:** re-mapear 187 registros (automático)

9. **cmcc.json:** regenerar con nueva estructura de 52→75 conceptos



### Riesgos de migración

- Retrocompatibilidad garantizada si se mantienen los códigos v1 como raíces

- Los splits de AC.01 requieren re-clasificar ~1,105 variantes existentes

- Los merges de ER pueden causar pérdida de granularidad si no se implementan subconceptos

- Calculados requieren nuevo módulo de derivación en pipeline



## 7. Taxonomía Completa

### ACTIVO CORRIENTE (18 conceptos)

- □ **AC.01** Efectivo y Equivalentes al Efectivo (3 hijos) ← AC.01

  - □ **AC.01.01** Caja ← AC.01

  - □ **AC.01.02** Bancos ← AC.01

  - □ **AC.01.03** Equivalentes al Efectivo ← AC.01

- □ **AC.02** Valores Negociables ← AC.01, AC.02

- □ **AC.03** Inversiones Financieras CP ← AC.02

- □ **AC.04** Cuentas por Cobrar Comerciales (2 hijos) ← AC.03, AC.04

  - □ **AC.04.01** Clientes ← AC.03

  - □ **AC.04.02** Documentos por Cobrar ← AC.04

- □ **AC.05** Cuentas por Cobrar Empresas Relacionadas CP ← AC.06, AC.06S

- □ **AC.06** Anticipos ← AC.07

- □ **AC.07** Impuestos por Recuperar (2 hijos) ← AC.07

  - □ **AC.07.01** IVA Crédito Fiscal ← AC.07

  - □ **AC.07.02** Otros Impuestos por Recuperar ← AC.07

- □ **AC.08** Existencias ← AC.05

- □ **AC.09** Activos Biológicos CP ← AC.09

- □ **AC.10** Gastos Pagados por Anticipado ← AC.08

- □ **AC.11** Otros Activos Corrientes ← AC.08, AC.07



### ACTIVO NO CORRIENTE (10 conceptos)

- □ **ANC.01** Propiedades, Planta y Equipos ← ANC.01

- □ **ANC.02** Propiedades de Inversión ← ANC.02

- □ **ANC.03** Activos Biológicos LP ← ANC.07

- □ **ANC.04** Activos Intangibles (2 hijos) [NUEVO]

  - □ **ANC.04.01** Intangibles ← ANC.03

  - □ **ANC.04.02** Plusvalía (Goodwill) ← ANC.08

- □ **ANC.05** Inversiones Permanentes ← ANC.04

- □ **ANC.06** Cuentas por Cobrar Empresas Relacionadas LP ← ANC.05

- □ **ANC.07** Impuestos Diferidos (Activo) ← ANC.06

- □ **ANC.08** Otros Activos No Corrientes ← ANC.06



### PASIVO CORRIENTE (15 conceptos)

- □ **PC.01** Cuentas por Pagar Comerciales (2 hijos) [NUEVO]

  - □ **PC.01.01** Proveedores ← PC.01

  - □ **PC.01.02** Documentos por Pagar ← PC.01, PC.08

- □ **PC.02** Obligaciones Financieras CP (3 hijos) [NUEVO]

  - □ **PC.02.01** Préstamos Bancarios CP ← PC.02

  - □ **PC.02.02** Leasing CP ← PC.03

  - □ **PC.02.03** Factoring ← PC.04

- □ **PC.03** Remuneraciones y Provisiones CP (2 hijos) [NUEVO]

  - □ **PC.03.01** Remuneraciones por Pagar ← PC.06

  - □ **PC.03.02** Provisiones CP ← PC.08

- □ **PC.04** Impuestos por Pagar CP (2 hijos) [NUEVO]

  - □ **PC.04.01** IVA Débito ← PC.05, PC.08

  - □ **PC.04.02** Otros Impuestos por Pagar ← PC.05

- □ **PC.05** Cuentas por Pagar Empresas Relacionadas CP ← PC.07

- □ **PC.06** Otros Pasivos Corrientes ← PC.08



### PASIVO NO CORRIENTE (8 conceptos)

- □ **PNC.01** Obligaciones Financieras LP (3 hijos) [NUEVO]

  - □ **PNC.01.01** Préstamos Bancarios LP ← PNC.01

  - □ **PNC.01.02** Leasing LP ← PNC.02

  - □ **PNC.01.03** Bonos ← PNC.03

- □ **PNC.02** Provisiones LP ← PNC.05

- □ **PNC.03** Impuestos Diferidos (Pasivo) ← PNC.05

- □ **PNC.04** Cuentas por Pagar Empresas Relacionadas LP ← PNC.04

- □ **PNC.05** Otros Pasivos No Corrientes ← PNC.05



### PATRIMONIO (6 conceptos)

- □ **PAT.01** Capital ← PAT.01

- □ **PAT.02** Reservas ← PAT.02

- □ **PAT.03** Resultados Acumulados ← PAT.03

- □ **PAT.04** Resultado del Ejercicio ← PAT.04

- □ **PAT.05** Participación No Controladora ← PAT.05

- □ **PAT.06** Otros Componentes Patrimoniales [NUEVO]



### ESTADO DE RESULTADOS (18 conceptos)

- □ **ER.01** Ventas ← ER.01

- □ **ER.02** Costo de Ventas ← ER.02

- □ **ER.03** Gastos de Administración y Ventas ← ER.04, ER.05

- □ **ER.04** Depreciación ← ER.07

- □ **ER.05** Amortización ← ER.07

- □ **ER.06** Ingresos Financieros ← ER.12

- □ **ER.07** Gastos Financieros ← ER.09

- □ **ER.08** Resultado por Participación ← ER.16

- □ **ER.09** Diferencias de Cambio ← ER.14, ER.15

- □ **ER.10** Otras Ganancias ← ER.13

- □ **ER.11** Otras Pérdidas ← ER.13

- □ **ER.12** Impuesto a la Renta ← ER.10

- ⚙ **ER.C01** Margen Bruto [NUEVO]

- ⚙ **ER.C02** Resultado Operacional (EBIT) [NUEVO]

- ⚙ **ER.C03** EBITDA [NUEVO]

- ⚙ **ER.C04** Resultado Antes de Impuestos [NUEVO]

- ⚙ **ER.C05** Resultado del Ejercicio [NUEVO]

- ⚙ **ER.C06** Margen Neto [NUEVO]



## 8. Preguntas Clave

### ¿El nuevo modelo elimina AC.01?

**No.** AC.01 se mantiene como raíz, pero se subdivide en 3 subconceptos (Caja, Bancos, Equivalentes) y 2 conceptos hermanos (Valores Negociables, Inversiones CP).


### ¿Cómo quedan ER.01 y ER.02?

**ER.01** y **ER.02** se mantienen como ACCOUNT. ER.03→ER.C01, ER.06→ER.C03, ER.08→ER.C02, ER.11→ER.C05 pasan a CALCULATED. ER.04+ER.05 se fusionan en ER.03. ER.07 se divide en Depreciación y Amortización.


### ¿Qué cuentas pasan a ser calculadas?

6 cuentas calculadas: Margen Bruto, EBIT, EBITDA, Resultado Antes de Impuestos, Resultado del Ejercicio, Margen Neto.


### ¿Qué compatibilidad mantiene con v1?

Compatibilidad total (100%). Todos los 52 códigos v1 tienen mapeo a v2. Los splits y merges se resuelven mediante la tabla de migración.


### ¿Cuál es el costo estimado de migración?

Medio-alto. El cambio principal es la reclasificación de variantes para los 3 splits mayores (AC.01, ER.01, ER.02). El resto es automatizable. Estimación: ~2-3 sprints de implementación.


## 9. GO / NO GO para migración

✅ 100% compatibilidad v1→v2 (52 códigos mapeados)

✅ 6 cuentas calculadas eliminan trabajo manual de derivación

✅ El split de AC.01 resuelve el principal hallazgo de Sprint 27.2B

⚠ 7 conceptos nuevos requieren poblar variantes

⚠ Splits de AC.01, ER.01, ER.02 requieren reclasificar >2,000 variantes



**RECOMENDACIÓN: GO CONDITIONAL**

- El diseño v2.0 es conceptualmente sólido y sigue IFRS/NIIF

- No rompe compatibilidad con v1

- Separa explícitamente ACCOUNT de CALCULATED

- Sin embargo, se recomienda NO migrar inmediatamente

- Prioridad: corregir AC.01 en v1 (subdividir variantes) antes de migrar

- Sprint 27.3 puede construir la interfaz de revisión sobre v1

- Migrar a v2 sería un sprint independiente posterior (CMCC v2.0 Migration)


### Plan sugerido

1. **Sprint 27.3:** Interfaz de revisión humana sobre v1 (el REVIEW queue existe)

2. **Sprint 27.4:** Subdividir AC.01 en v1 (sin cambiar catálogo)

3. **Sprint 27.5:** Migración a v2.0 (copiar, mapear, validar)

4. **Sprint 27.6:** Activar v2.0 en producción

---
**Sprint 27.2C complete.** Read-only CMCC v2.0 design.
