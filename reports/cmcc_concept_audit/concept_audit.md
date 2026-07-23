# CMCC Concept Audit — Sprint 27.2B

**Generated:** 2026-07-10 19:46:49 UTC
**Source:** `cmcc.json` (52 concepts, 3064 variants)
---
*Read-only. No production modifications.*


## 1. Overview

- **52** concepts analyzed

- **48** concepts with variants, **4** empty

- **3064** total variants across all concepts

- **2969** unique normalized tokens


## 2. Cohesion Analysis

Cohesion Index = mean_jaccard - 0.5*std_jaccard + 0.1*min(1, n_variants/100)

Range: 0 = maximally diverse, 1 = maximally cohesive



| Rank | Concept | Name | Cohesion | Variants | Mean J | Std J |

|---|---|---|---|---|---|---|

| 1 | AC.02 | Inversiones Corto Plazo | 0.0 | 10 | 0.0248 | 0.0711 |

| 2 | ANC.03 | Intangibles | 0.0 | 12 | 0.0167 | 0.0947 |

| 3 | PNC.05 | Otros Pasivos LP | 0.0 | 11 | 0.0491 | 0.1284 |

| 4 | PC.07 | Relacionadas CP | 0.0 | 7 | 0.0943 | 0.2198 |

| 5 | PAT.02 | Reservas | 0.0 | 16 | 0.0239 | 0.0833 |

| 6 | AC.09 | Activos Biológicos CP | 0.0 | 4 | 0.0833 | 0.1863 |

| 7 | ANC.08 | Plusvalía (Goodwill) | 0.0 | 5 | 0.0333 | 0.1 |

| 8 | ANC.07 | Activos Biológicos LP | 0.0 | 8 | 0.0089 | 0.0464 |

| 9 | PAT.05 | Participaciones No Controladoras | 0.004 | 4 | 0.0 | 0.0 |

| 10 | AC.04 | Documentos por Cobrar | 0.0044 | 11 | 0.097 | 0.207 |

| 11 | ANC.04 | Inversiones Permanentes | 0.0054 | 6 | 0.0611 | 0.1235 |

| 12 | AC.08 | Otros Activos Corrientes | 0.006 | 6 | 0.0 | 0.0 |

| 13 | ER.14 | Corrección Monetaria y Reajustes | 0.008 | 14 | 0.0883 | 0.1887 |

| 14 | ER.13 | Otras Ganancias y Pérdidas | 0.0086 | 18 | 0.0634 | 0.1456 |

| 15 | PNC.01 | Obligaciones Bancarias LP | 0.0091 | 13 | 0.0656 | 0.1391 |



**40 concepts with low cohesion (<0.3):**

- AC.02 (Inversiones Corto Plazo): 0.0 — variants are semantically diverse

- ANC.03 (Intangibles): 0.0 — variants are semantically diverse

- PNC.05 (Otros Pasivos LP): 0.0 — variants are semantically diverse

- PC.07 (Relacionadas CP): 0.0 — variants are semantically diverse

- PAT.02 (Reservas): 0.0 — variants are semantically diverse

- AC.09 (Activos Biológicos CP): 0.0 — variants are semantically diverse

- ANC.08 (Plusvalía (Goodwill)): 0.0 — variants are semantically diverse

- ANC.07 (Activos Biológicos LP): 0.0 — variants are semantically diverse

- PAT.05 (Participaciones No Controladoras): 0.004 — variants are semantically diverse

- AC.04 (Documentos por Cobrar): 0.0044 — variants are semantically diverse

- ANC.04 (Inversiones Permanentes): 0.0054 — variants are semantically diverse

- AC.08 (Otros Activos Corrientes): 0.006 — variants are semantically diverse

- ER.14 (Corrección Monetaria y Reajustes): 0.008 — variants are semantically diverse

- ER.13 (Otras Ganancias y Pérdidas): 0.0086 — variants are semantically diverse

- PNC.01 (Obligaciones Bancarias LP): 0.0091 — variants are semantically diverse

- PAT.03 (Utilidades Retenidas): 0.0091 — variants are semantically diverse

- PC.08 (Otros Pasivos Corrientes): 0.0106 — variants are semantically diverse

- AC.06S (Cta. Cte. Socios / Retiros (Activo)): 0.0107 — variants are semantically diverse

- ANC.06 (Otros Activos No Corrientes): 0.0108 — variants are semantically diverse

- AC.05 (Inventarios): 0.0137 — variants are semantically diverse

- AC.06 (Relacionadas CP): 0.0154 — variants are semantically diverse

- ANC.05 (Relacionadas LP): 0.0224 — variants are semantically diverse

- ER.07 (Depreciación y Amortización): 0.0275 — variants are semantically diverse

- ER.12 (Ingresos Financieros): 0.0316 — variants are semantically diverse

- AC.07 (Otras Cuentas por Cobrar CP): 0.0331 — variants are semantically diverse

- PC.06 (Remuneraciones por Pagar): 0.0353 — variants are semantically diverse

- PC.02 (Obligaciones Bancarias CP): 0.0355 — variants are semantically diverse

- ANC.01 (Activo Fijo): 0.0388 — variants are semantically diverse

- PC.05 (Impuestos por Pagar): 0.0404 — variants are semantically diverse

- AC.03 (Clientes): 0.0437 — variants are semantically diverse

- PC.01 (Proveedores): 0.0521 — variants are semantically diverse

- PAT.01 (Capital): 0.0546 — variants are semantically diverse

- ER.09 (Gastos Financieros): 0.0681 — variants are semantically diverse

- ER.04 (Gastos de Administración): 0.074 — variants are semantically diverse

- PAT.04 (Resultado del Ejercicio): 0.0816 — variants are semantically diverse

- AC.01 (Caja y Bancos): 0.0855 — variants are semantically diverse

- ER.02 (Costo de Ventas): 0.0882 — variants are semantically diverse

- ER.01 (Ventas): 0.095 — variants are semantically diverse

- ER.16 (Resultado Método Participación): 0.2199 — variants are semantically diverse

- ER.05 (Gastos de Venta): 0.2237 — variants are semantically diverse



## 3. Concept Similarity (Separability)

**1 concept pairs with similarity > 0.4** (potential merge candidates)



| Rank | Concept A | A Name | Concept B | B Name | Jaccard |

|---|---|---|---|---|---|

| 1 | PC.03 | Leasing CP | PNC.02 | Leasing LP | 0.6 |



## 4. Risk Ranking

| Rank | Concept | Name | Risk | Variants | Review | Cohesion | Overlap | Action |

|---|---|---|---|---|---|---|---|---|

| 1 | AC.01 | Caja y Bancos | 73.13 | 1105 | 152 | 0.0855 | 0.2746 | SPLIT |

| 2 | ER.01 | Ventas | 67.68 | 644 | 51 | 0.095 | 0.5217 | SPLIT |

| 3 | ER.02 | Costo de Ventas | 63.33 | 501 | 18 | 0.0882 | 0.4588 | SPLIT |

| 4 | AC.09 | Activos Biológicos CP | 63.0 | 4 | 0 | 0.0 | 0.9 | MERGE → AC.09 ⚠|

| 5 | PAT.05 | Participaciones No Controladoras | 58.21 | 4 | 0 | 0.004 | 0.6667 | MERGE → PAT.05 ⚠|

| 6 | ER.07 | Depreciación y Amortización | 57.51 | 4 | 0 | 0.0275 | 0.6667 | EXPAND ⚠|

| 7 | PC.03 | Leasing CP | 52.14 | 4 | 0 | 0.4285 | 1.0 | MERGE → PC.03 ⚠|

| 8 | PC.07 | Relacionadas CP | 50.0 | 7 | 0 | 0.0 | 1.0 | NO ACTION |

| 9 | PNC.02 | Leasing LP | 49.94 | 2 | 0 | 0.502 | 1.0 | MERGE → PNC.02 ⚠|

| 10 | PNC.04 | Relacionadas LP | 49.64 | 4 | 0 | 0.5121 | 1.0 | EXPAND ⚠|

| 11 | PC.01 | Proveedores | 49.53 | 74 | 23 | 0.0521 | 0.7547 | REVIEW |

| 12 | ER.13 | Otras Ganancias y Pérdidas | 48.3 | 18 | 1 | 0.0086 | 0.9231 | NO ACTION |

| 13 | PNC.01 | Obligaciones Bancarias LP | 48.06 | 13 | 0 | 0.0091 | 0.9167 | NO ACTION |

| 14 | AC.07 | Otras Cuentas por Cobrar CP | 47.8 | 53 | 0 | 0.0331 | 0.8072 | NO ACTION |

| 15 | PC.08 | Otros Pasivos Corrientes | 47.27 | 35 | 0 | 0.0106 | 0.8793 | NO ACTION |



## 5. Action Recommendations

| Action | Concepts |

|---|---|

| SPLIT | 3 — AC.01, ER.01, ER.02 |

| REVIEW | 1 — PC.01 |

| EXPAND | 6 — ANC.02, PNC.04, ER.03, ER.06, ER.07, ER.08 |

| NO ACTION | 24 — AC.03, AC.05, AC.06, AC.06S, AC.07, ANC.01, ANC.03, ANC.06, PC.02, PC.04... |



| Rank | Concept | Name | Action | Risk | Variants | Cohesion |

|---|---|---|---|---|---|---|

| 1 | ANC.02 | Propiedades de Inversión | EXPAND | 15.0 | 0 | 1.0 |

| 2 | PNC.04 | Relacionadas LP | EXPAND | 49.64 | 4 | 0.5121 |

| 3 | ER.03 | Margen Bruto | EXPAND | 15.0 | 0 | 1.0 |

| 4 | ER.06 | EBITDA | EXPAND | 15.0 | 0 | 1.0 |

| 5 | ER.07 | Depreciación y Amortización | EXPAND | 57.51 | 4 | 0.0275 |

| 6 | ER.08 | Resultado Operacional | EXPAND | 15.0 | 0 | 1.0 |

| 7 | AC.02 | Inversiones Corto Plazo | MERGE → AC.02 | 46.19 | 10 | 0.0 |

| 8 | AC.04 | Documentos por Cobrar | MERGE → AC.04 | 46.12 | 11 | 0.0044 |

| 9 | AC.08 | Otros Activos Corrientes | MERGE → AC.08 | 46.07 | 6 | 0.006 |

| 10 | AC.09 | Activos Biológicos CP | MERGE → AC.09 | 63.0 | 4 | 0.0 |

| 11 | ANC.04 | Inversiones Permanentes | MERGE → ANC.04 | 45.84 | 6 | 0.0054 |

| 12 | ANC.05 | Relacionadas LP | MERGE → ANC.05 | 47.22 | 9 | 0.0224 |

| 13 | ANC.08 | Plusvalía (Goodwill) | MERGE → ANC.08 | 40.0 | 5 | 0.0 |

| 14 | ER.05 | Gastos de Venta | MERGE → ER.05 | 43.29 | 5 | 0.2237 |

| 15 | ER.10 | Impuesto a la Renta | MERGE → ER.10 | 35.0 | 1 | 1.0 |

| 16 | ER.11 | Utilidad Neta | MERGE → ER.11 | 35.1 | 1 | 1.0 |

| 17 | ER.15 | Diferencias de Cambio | MERGE → ER.15 | 33.46 | 8 | 0.329 |

| 18 | ER.16 | Resultado Método Participación | MERGE → ER.16 | 37.4 | 7 | 0.2199 |

| 19 | PAT.04 | Resultado del Ejercicio | MERGE → PAT.04 | 41.84 | 5 | 0.0816 |

| 20 | PAT.05 | Participaciones No Controladoras | MERGE → PAT.05 | 58.21 | 4 | 0.004 |

| 21 | PC.03 | Leasing CP | MERGE → PC.03 | 52.14 | 4 | 0.4285 |

| 22 | PNC.02 | Leasing LP | MERGE → PNC.02 | 49.94 | 2 | 0.502 |

| 23 | PNC.03 | Bonos | MERGE → PNC.03 | 21.67 | 1 | 1.0 |

| 24 | PNC.05 | Otros Pasivos LP | MERGE → PNC.05 | 45.65 | 11 | 0.0 |

| 49 | PC.01 | Proveedores | REVIEW | 49.53 | 74 | 0.0521 |

| 50 | AC.01 | Caja y Bancos | SPLIT | 73.13 | 1105 | 0.0855 |

| 51 | ER.01 | Ventas | SPLIT | 67.68 | 644 | 0.095 |

| 52 | ER.02 | Costo de Ventas | SPLIT | 63.33 | 501 | 0.0882 |



## 6. AC.01 Deep Dive

- **1105** variants (largest concept by far)

- **Cohesion Index:** 0.0855

- **Mean Jaccard:** 0.0094

- **Lexical Diversity:** 1.6643

- **Entropy:** 9.5785

- **Overlap Ratio:** 0.2746 (vocabulary shared with other concepts)

- **REVIEW queue entries:** 152 (58.69% of total REVIEW)

- **Gold standard records:** 18



⚠ **AC.01 has LOW cohesion.** Its variants span: Caja, Banco, Cuenta Corriente, but also Anticipos, Valores, Garantías, Fondos Mutuos, etc.

**Recommendation: SPLIT** AC.01 into sub-concepts (AC.01a Caja/Bancos, AC.01b Valores Negociables, AC.01c Otros Efectivos)



## 7. Detailed Concept Audit (All 52 Concepts)

| Code | Name | Variants | Cohesion | Risk | Action | GS | Dic | Review |

|---|---|---|---|---|---|---|---|---|

| AC.01 | Caja y Bancos | 1105 | 0.0855 | 73.13 | SPLIT | 18 | 28 | 152 |

| ER.01 | Ventas | 644 | 0.095 | 67.68 | SPLIT | 4 | 15 | 51 |

| ER.02 | Costo de Ventas | 501 | 0.0882 | 63.33 | SPLIT | 0 | 45 | 18 |

| AC.09 | Activos Biológicos CP | 4 | 0.0 | 63.0 | MERGE → AC.09 | 0 | 6 | 0 |

| PAT.05 | Participaciones No Controladoras | 4 | 0.004 | 58.21 | MERGE → PAT.05 | 0 | 5 | 0 |

| ER.07 | Depreciación y Amortización | 4 | 0.0275 | 57.51 | EXPAND | 4 | 5 | 0 |

| PC.03 | Leasing CP | 4 | 0.4285 | 52.14 | MERGE → PC.03 | 0 | 4 | 0 |

| PC.07 | Relacionadas CP | 7 | 0.0 | 50.0 | NO ACTION | 3 | 7 | 0 |

| PNC.02 | Leasing LP | 2 | 0.502 | 49.94 | MERGE → PNC.02 | 0 | 2 | 0 |

| PNC.04 | Relacionadas LP | 4 | 0.5121 | 49.64 | EXPAND | 1 | 4 | 0 |

| PC.01 | Proveedores | 74 | 0.0521 | 49.53 | REVIEW | 7 | 11 | 23 |

| ER.13 | Otras Ganancias y Pérdidas | 18 | 0.0086 | 48.3 | NO ACTION | 4 | 21 | 1 |

| PNC.01 | Obligaciones Bancarias LP | 13 | 0.0091 | 48.06 | NO ACTION | 1 | 13 | 0 |

| AC.07 | Otras Cuentas por Cobrar CP | 53 | 0.0331 | 47.8 | NO ACTION | 15 | 53 | 0 |

| PC.08 | Otros Pasivos Corrientes | 35 | 0.0106 | 47.27 | NO ACTION | 7 | 35 | 0 |

| ANC.05 | Relacionadas LP | 9 | 0.0224 | 47.22 | MERGE → ANC.05 | 0 | 9 | 0 |

| ANC.06 | Otros Activos No Corrientes | 24 | 0.0108 | 46.42 | NO ACTION | 4 | 24 | 0 |

| AC.02 | Inversiones Corto Plazo | 10 | 0.0 | 46.19 | MERGE → AC.02 | 0 | 10 | 0 |

| AC.04 | Documentos por Cobrar | 11 | 0.0044 | 46.12 | MERGE → AC.04 | 0 | 11 | 0 |

| AC.08 | Otros Activos Corrientes | 6 | 0.006 | 46.07 | MERGE → AC.08 | 0 | 7 | 0 |

| AC.03 | Clientes | 24 | 0.0437 | 46.06 | NO ACTION | 8 | 25 | 0 |

| ANC.07 | Activos Biológicos LP | 8 | 0.0 | 46.0 | NO ACTION | 2 | 9 | 0 |

| ER.04 | Gastos de Administración | 89 | 0.074 | 45.92 | NO ACTION | 13 | 90 | 2 |

| ANC.04 | Inversiones Permanentes | 6 | 0.0054 | 45.84 | MERGE → ANC.04 | 0 | 6 | 0 |

| PNC.05 | Otros Pasivos LP | 11 | 0.0 | 45.65 | MERGE → PNC.05 | 0 | 11 | 0 |

| ER.09 | Gastos Financieros | 24 | 0.0681 | 45.6 | NO ACTION | 12 | 25 | 0 |

| ER.12 | Ingresos Financieros | 7 | 0.0316 | 45.05 | NO ACTION | 3 | 8 | 0 |

| ER.14 | Corrección Monetaria y Reajustes | 14 | 0.008 | 45.0 | NO ACTION | 2 | 14 | 0 |

| ANC.01 | Activo Fijo | 62 | 0.0388 | 44.99 | NO ACTION | 21 | 62 | 0 |

| AC.06S | Cta. Cte. Socios / Retiros (Activo) | 15 | 0.0107 | 44.41 | NO ACTION | 2 | 16 | 0 |

| PAT.01 | Capital | 45 | 0.0546 | 44.26 | NO ACTION | 8 | 9 | 10 |

| PAT.03 | Utilidades Retenidas | 11 | 0.0091 | 43.73 | NO ACTION | 4 | 11 | 0 |

| PC.02 | Obligaciones Bancarias CP | 28 | 0.0355 | 43.73 | NO ACTION | 7 | 28 | 0 |

| PC.05 | Impuestos por Pagar | 34 | 0.0404 | 43.43 | NO ACTION | 12 | 35 | 1 |

| ER.05 | Gastos de Venta | 5 | 0.2237 | 43.29 | MERGE → ER.05 | 0 | 5 | 0 |

| AC.05 | Inventarios | 33 | 0.0137 | 42.8 | NO ACTION | 5 | 33 | 0 |

| PAT.02 | Reservas | 16 | 0.0 | 42.5 | NO ACTION | 1 | 16 | 0 |

| PC.06 | Remuneraciones por Pagar | 37 | 0.0353 | 42.27 | NO ACTION | 16 | 38 | 0 |

| PAT.04 | Resultado del Ejercicio | 5 | 0.0816 | 41.84 | MERGE → PAT.04 | 0 | 5 | 0 |

| AC.06 | Relacionadas CP | 15 | 0.0154 | 41.76 | NO ACTION | 1 | 15 | 0 |

| ANC.03 | Intangibles | 12 | 0.0 | 41.67 | NO ACTION | 1 | 12 | 0 |

| ANC.08 | Plusvalía (Goodwill) | 5 | 0.0 | 40.0 | MERGE → ANC.08 | 0 | 5 | 0 |

| ER.16 | Resultado Método Participación | 7 | 0.2199 | 37.4 | MERGE → ER.16 | 0 | 8 | 0 |

| ER.11 | Utilidad Neta | 1 | 1.0 | 35.1 | MERGE → ER.11 | 0 | 1 | 1 |

| ER.10 | Impuesto a la Renta | 1 | 1.0 | 35.0 | MERGE → ER.10 | 0 | 3 | 0 |

| ER.15 | Diferencias de Cambio | 8 | 0.329 | 33.46 | MERGE → ER.15 | 0 | 9 | 0 |

| PC.04 | Factoring | 8 | 0.3689 | 31.66 | NO ACTION | 1 | 8 | 0 |

| PNC.03 | Bonos | 1 | 1.0 | 21.67 | MERGE → PNC.03 | 0 | 1 | 0 |

| ANC.02 | Propiedades de Inversión | 0 | 1.0 | 15.0 | EXPAND | 0 | 0 | 0 |

| ER.03 | Margen Bruto | 0 | 1.0 | 15.0 | EXPAND | 0 | 0 | 0 |

| ER.06 | EBITDA | 0 | 1.0 | 15.0 | EXPAND | 0 | 0 | 0 |

| ER.08 | Resultado Operacional | 0 | 1.0 | 15.0 | EXPAND | 0 | 0 | 0 |



## 8. Findings & Risks

- **AC.01** (Caja y Bancos): Risk=73.13, Action=SPLIT, Cohesion=0.0855, 1105 variants, 152 REVIEW

- **ER.01** (Ventas): Risk=67.68, Action=SPLIT, Cohesion=0.095, 644 variants, 51 REVIEW

- **ER.02** (Costo de Ventas): Risk=63.33, Action=SPLIT, Cohesion=0.0882, 501 variants, 18 REVIEW

- **AC.09** (Activos Biológicos CP): Risk=63.0, Action=MERGE → AC.09, Cohesion=0.0, 4 variants, 0 REVIEW

- **PAT.05** (Participaciones No Controladoras): Risk=58.21, Action=MERGE → PAT.05, Cohesion=0.004, 4 variants, 0 REVIEW

- **ER.07** (Depreciación y Amortización): Risk=57.51, Action=EXPAND, Cohesion=0.0275, 4 variants, 0 REVIEW

- **PC.03** (Leasing CP): Risk=52.14, Action=MERGE → PC.03, Cohesion=0.4285, 4 variants, 0 REVIEW

- **PC.07** (Relacionadas CP): Risk=50.0, Action=NO ACTION, Cohesion=0.0, 7 variants, 0 REVIEW

- **PNC.02** (Leasing LP): Risk=49.94, Action=MERGE → PNC.02, Cohesion=0.502, 2 variants, 0 REVIEW

- **PNC.04** (Relacionadas LP): Risk=49.64, Action=EXPAND, Cohesion=0.5121, 4 variants, 0 REVIEW



**4 empty concepts:** ANC.02, ER.03, ER.06, ER.08



**1 high-similarity pairs:** PC.03↔PNC.02(0.6)



## 9. GO / NO GO for Sprint 27.3 (Human Review)



❌ 8 concepts with risk > 50: AC.01, ER.01, ER.02, AC.09, PAT.05

❌ 3 concepts recommended for SPLIT: AC.01, ER.01, ER.02

❌ 4 empty concepts exist: ANC.02, ER.03, ER.06, ER.08

❌ AC.01 cohesion too low (0.0855) — need SPLIT before review



**RECOMMENDATION: NO GO** — address concept quality issues before building human review interface

**Priority actions:**

1. SPLIT over-generalized concepts: AC.01, ER.01, ER.02

2. Populate empty concepts: ANC.02, ER.03, ER.06, ER.08

3. Merge highly similar concepts: AC.02, AC.04, AC.08, AC.09, ANC.04, ANC.05, ANC.08, ER.05, ER.10, ER.11, ER.15, ER.16, PAT.04, PAT.05, PC.03, PNC.02, PNC.03, PNC.05

4. Re-assess concept quality after fixes, then proceed to Sprint 27.3



### Generated Files

- `concept_cohesion.xlsx` (8,381 bytes)

- `concept_similarity.xlsx` (25,089 bytes)

- `concept_actions.xlsx` (7,869 bytes)

- `concept_audit.xlsx` (11,913 bytes)

- `concept_statistics.json` (2,828 bytes)

- `concept_risk.xlsx` (8,297 bytes)

---

**Sprint 27.2B complete.** Read-only. No production modifications.
