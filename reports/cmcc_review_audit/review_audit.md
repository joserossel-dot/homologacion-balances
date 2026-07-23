# CMCC Review Audit — Sprint 27.2
**Generated:** 2026-07-10 19:35:51 UTC
**Source:** `review_queue.xlsx` (259 entries)
---
*Read-only analytical phase.*


## 1. Unique Decisions (Q1)

- **Total REVIEW entries:** 259

- **Unique account_names:** 239

- **Unique matched_variants:** 204 ← **real human decisions**

- **Unique concepts:** 9

- **Unique companies:** 7

- **Unique documents:** 9

> **Answer:** **204 decisions** (one per unique variant), not 259. Savings: 55 (21.24%).


## 2. Variant Frequency (Q2)

### Top 10 frequent variants

| # | Variant | Freq | Concept | Cos | Docs | % |

|---|---|---|---|---|---|---|

| 1 | INVERSIONES Y ASESORIAS GUAYACAN S.A. Página | 6 | AC.01 | 1 | 1 | 2.32% |

| 2 | anivel | 4 | ER.01 | 1 | 1 | 1.54% |

| 3 | rengo | 4 | ER.01 | 1 | 3 | 1.54% |

| 4 | (=) MARGEN DE LA EXPLOTACION | 3 | AC.01 | 2 | 3 | 1.16% |

| 5 | Reajuste PPM-IVA | 3 | AC.01 | 1 | 3 | 1.16% |

| 6 | Enero a Diciembre | 3 | AC.01 | 1 | 3 | 1.16% |

| 7 | o DIRECCION AVDA, LOS CONQUISTADORES 1700 FOL | 3 | AC.01 | 1 | 1 | 1.16% |

| 8 | documentos | 3 | ER.01 | 1 | 1 | 1.16% |

| 9 | : De la Página Anterior | 2 | AC.01 | 1 | 1 | 0.77% |

| 10 | Construcciones y obras de infraestructura | 2 | AC.01 | 2 | 2 | 0.77% |


**Top 20:** 20 variants cover 53 entries
**Top 50:** 50 variants cover 105 entries


## 3. Pareto (Q3)

| Milestone | Variants | Entries | % |

|---|---|---|---|

| Top 5 | 5 | 20 | 7.72% |

| Top 10 | 10 | 33 | 12.74% |

| Top 20 | 20 | 53 | 20.46% |

| Top 50 | 50 | 105 | 40.54% |

| Top 100 | 100 | 155 | 59.85% |

| Pareto 80% | rank 153 | 208 | 80.31% |

| Pareto 90% | rank 179 | 234 | 90.35% |

| Pareto 95% | rank 192 | 247 | 95.37% |

> **Answer:** 80% of REVIEW covered by **~12.74%** with top 10 variants. 90% at **~20.46%**. 95% at **~40.54%**.


## 4. Concept Distribution (Q4)

| Code | Name | Count | % | Variants | Companies | Docs |

|---|---|---|---|---|---|---|

| AC.01 | Caja y Bancos | 152 | 58.69% | 120 | 7 | 9 |

| ER.01 | Ventas | 51 | 19.69% | 32 | 7 | 9 |

| PC.01 | Proveedores | 23 | 8.88% | 23 | 6 | 7 |

| ER.02 | Costo de Ventas | 18 | 6.95% | 14 | 6 | 7 |

| PAT.01 | Capital | 10 | 3.86% | 10 | 4 | 4 |

| ER.04 | Gastos de Administración | 2 | 0.77% | 2 | 1 | 1 |

| ER.11 | Utilidad Neta | 1 | 0.39% | 1 | 1 | 1 |

| ER.13 | Otras Ganancias y Pérdidas | 1 | 0.39% | 1 | 1 | 1 |

| PC.05 | Impuestos por Pagar | 1 | 0.39% | 1 | 1 | 1 |

> ⚠ DOMINANT: `AC.01` (Caja y Bancos) = 58.69% of REVIEW


## 5. Matching Method Distribution (Q5)

| Method | Count | % | Variants | Companies | Docs |

|---|---|---|---|---|---|

| cmcc_variante | 259 | 100.0% | 204 | 7 | 9 |

> **Answer:** 100% of REVIEW = **cmcc_variante**. No dictionary/rule/shadow entries at score=1.0.


## 6. Coverage Simulation (Q6)

**Current:** 556 classified / 445 UNKNOWN = 34.19%


| Scenario | New Classified | Total Classified | Coverage | Delta | Remaining UNKNOWN |

|---|---|---|---|---|---|

| Approve one decision per unique variant | 204 | 760 | 46.74% | +12.55pp | 241 |

| Approve per unique account_name | 239 | 795 | 48.89% | +14.7pp | 206 |

| Approve all REVIEW entries | 259 | 815 | 50.12% | +15.93pp | 186 |

> **Answer:** Variant-level approval: 34.19% → **46.74%** (+12.55pp), 241 UNKNOWN remaining.


## 7. Company Distribution (Q7)

| # | Company | REVIEW | % | Concepts | Variants | Docs |

|---|---|---|---|---|---|---|

| 1 | BALANCE ORIGINAL | 118 | 45.56% | 7 | 95 | 1 |

| 2 | Balance | 69 | 26.64% | 5 | 53 | 3 |

| 3 | Balance Agricola El Comino dic | 19 | 7.34% | 5 | 18 | 1 |

| 4 | balance general guayacan | 19 | 7.34% | 5 | 14 | 1 |

| 5 | EEFF - | 14 | 5.41% | 4 | 14 | 1 |

| 6 | BALANCE CLASIFICADO AICSA | 11 | 4.25% | 4 | 11 | 1 |

| 7 | Balance Clasificado y Estado resultado | 9 | 3.47% | 4 | 9 | 1 |



## 8. Document & Layout Distribution (Q8)

| # | Document | Layout | REVIEW | % | Concepts | Variants |

|---|---|---|---|---|---|---|---|

| 1 | BALANCE ORIGINAL 2014.pdf | pdf_estandar | 118 | 45.56% | 7 | 95 |

| 2 | Balance 2015 - Soc Com e Inv Campoamor SA.pdf | pdf_estandar | 32 | 12.36% | 4 | 32 |

| 3 | balance general guayacan 2020.pdf | pdf_estandar | 19 | 7.34% | 5 | 14 |

| 4 | Balance 2016 Campomanes S A .pdf | pdf_estandar | 19 | 7.34% | 5 | 18 |

| 5 | Balance Agricola El Comino dic 2018.pdf | pdf_estandar | 19 | 7.34% | 5 | 18 |

| 6 | Balance 2015 - Transp Libardon Ltda.pdf | pdf_estandar | 18 | 6.95% | 2 | 18 |

| 7 | EEFF - 2018 Los Nogales.pdf | pdf_estandar | 14 | 5.41% | 4 | 14 |

| 8 | BALANCE CLASIFICADO AICSA 2019.pdf | pdf_estandar | 11 | 4.25% | 4 | 11 |

| 9 | Balance Clasificado y Estado resultado 2017 I | pdf_estandar | 9 | 3.47% | 4 | 9 |


> **Answer:** Single layout `pdf_estandar` for all REVIEW. Top doc `BALANCE ORIGINAL 2014.pdf` = 118 entries (45.56%).


## 9. Human Effort (Q9)

**Comparison:** Review by entries (259) vs review by variants (204)


| Scenario | All Variants | Top 20 | Top 50 | Pareto80 | Pareto90 | Pareto95 | All Entries | Savings |

|---|---|---|---|---|---|---|---|---|---|

| A (30s/variant) | 1.7h | 0.17h | 0.42h | 1.27h | 1.49h | 1.6h | 2.16h | 21.24% |

| B (1min/variant) | 3.4h | 0.33h | 0.83h | 2.55h | 2.98h | 3.2h | 4.32h | 21.24% |

| C (2min/variant) | 6.8h | 0.67h | 1.67h | 5.1h | 5.97h | 6.4h | 8.63h | 21.24% |



## 10. Recommendation (Q10)

**Best approach:** Review by concept (dominant concept >50% of REVIEW)

**GO / NO GO:** NO GO (risks identified)



### ROI Analysis

- Savings vs account-level: 21.24%

- Pareto80: 153 variants, 80.31% coverage

- Pareto90: 179 variants, 90.35% coverage

- Pareto95: 192 variants, 95.37% coverage

- Dominant concept: AC.01 (58.69%)

- Dominant company: BALANCE ORIGINAL (45.56%)



### Recommended Workflow

1. Review 153 Pareto80 variants first (80.31% coverage)

2. Apply approved variant rules globally (each variant → one concept)

3. Flag ambiguous accounts (same name → multiple concepts) for manual review

4. Batch remaining low-frequency variants for periodic review



### Risks

- High concentration on AC.01 (58.69%) — verify CMCC quality



### Effort Summary

- Scenario A (30s/variant): 1.7h total

- Scenario B (1min/variant): 3.4h total

- Scenario C (2min/variant): 6.8h total



### Validations

- ✓ All variants map to exactly one concept

- ✓ No account maps to multiple concepts

- ✓ All scores = 1.0 (expected)


**Status:** PASS


### Generated Files

- `review_unique.xlsx` (5015 bytes)

- `variant_frequency.xlsx` (8686 bytes)

- `concept_distribution.xlsx` (5839 bytes)

- `company_distribution.xlsx` (5452 bytes)

- `document_distribution.xlsx` (5583 bytes)

- `pareto.xlsx` (17054 bytes)

- `coverage_simulation.xlsx` (5085 bytes)

- `human_effort.xlsx` (5129 bytes)

- `matching_method_distribution.xlsx` (4946 bytes)


---
**Sprint 27.2 complete.** Read-only. No production modifications.
