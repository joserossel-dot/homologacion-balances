# CMCC Official Benchmark — Pipeline Actual vs Pipeline + CMCC

**Generated:** 2026-07-10 18:25:28 UTC

**Gold Standard:** 46 accounts matched (baseline) / 46 accounts matched (candidate)

**Configuration:** Baseline: ENABLE_CMCC=False | Candidate: ENABLE_CMCC=True, PRODUCTION=True, threshold=0.95

---

## 1. Executive Summary

| Metric | Baseline | Candidate | Δ | Δ% |

|---|---|---|---|---|

| Total accounts | 1626 | 1626 | — | — |

| Classified | 556 | 556 | 0 | 0.0% |

| UNKNOWN | 445 | 186 | -259 | -58.2% |

| Coverage | 34.19% | 34.19% | 0.0pp | — |

| Processing time | 88.354s | 98.588s | 10.234s | 11.6% |



## 2. Gold Standard Metrics

| Metric | Baseline | Candidate | Δ |

|---|---|---|---|

| accuracy_pct | 100.0 | 100.0 | 0.0 |

| macro_f1 | 1.0 | 1.0 | 0.0 |

| micro_f1 | 1.0 | 1.0 | 0.0 |

| macro_precision | 1.0 | 1.0 | 0.0 |

| macro_recall | 1.0 | 1.0 | 0.0 |

| Correct | 46 / 46 | 46 / 46 | — |

| Errors | 0 | 0 | — |



## 3. Error Distribution

*No errors detected.*



## 4. Pipeline Comparison (All Accounts)

**Total accounts compared:** 517

**Changed classifications:** 242 (46.81% of total)

**Unchanged:** 275



### Changed Accounts (Top 50)

| # | Account | Baseline Code | Baseline Method | Candidate Code | Candidate Method |

|---|---|---|---|---|---|

| 1 | GM ———omeccion AVDA. LOSCONQUISTADORES 1700 FOLIO  | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 2 | l ANTICIFO PERSONAL: | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 3 | CORRESPONDENCIA | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 4 | MARGEN DE EXPLOTACION (BRUTO) | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 5 | E Enero a Diciembre | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 6 | hd : GRATIFICACION | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 7 | o. COMUNICACIONES | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 8 | o OTROS GASTOS E | UNKNOWN | unclassified | ER.13 | cmcc_variante |

| 9 | Anticipo Proveedores 53,414 Retenciones | UNKNOWN | unclassified | PC.01 | cmcc_variante |

| 10 | | CORP BANCA LOS ANGELES 2.355,58 CUENTAS POR PAGA | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 11 | INGRESOS DE EXPLOTACIÓN | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 12 | FORM | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 13 | : MAQUINARIA 579.394.650 1.698.296 — | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 14 | Documentos y cuentas por pagar empresas relacionad | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 15 | Al 31 de Diciembre de | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 16 | EBITDA | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 17 | Materiales de Taller | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 18 | CLIENTES CAMPOMANES 71.271.257 CUENTAS POR PAGAR | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 19 | Bono | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 20 | Comunicaciones | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 21 | TELEFONO RED FIA | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 22 | 0 DIRECCION — AYDA. LOS CONQUISTADORES 1700 FOLIO  | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 23 | Gastos Menores | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 24 | GTA. CTE CLIENTES “RO18.047.831 — | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 25 | CAJA CHICA 100.000 CUENTAS POR PAGAR EMPRESA RELAC | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 26 | : GASTOSOPERACIONALES — | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 27 | o 65 SALDO A FAVOR 85 1531842 + 68 Impuesto Adeuda | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 28 | E CORRESPONDENCIA | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 29 | Disponible | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 30 | eo HONORARIOS POR | UNKNOWN | unclassified | PC.01 | cmcc_variante |

| 31 | ASEO | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 32 | RESERVA REVALORIZ. CAPITAL PROPIO | UNKNOWN | unclassified | PAT.01 | cmcc_variante |

| 33 | e COMISIONES | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 34 | e PROVISION INTERESES | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 35 | 72 MAS: intereses y Multas | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 36 | Electricidad | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 37 | a CAJA DECOMPENSACION — | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 38 | ELECTRICIDAD | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| 39 | 65 SALDO A FAVOR 85 17504249 + 68 Impuesto Adeudad | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 40 | Construcciones y obras de infraestructura | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 41 | Asignacion Familiar | AC.01 | code | AC.07 | cmcc_variante |

| 42 | Desde Enero Hasta Diclembre de | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 43 | OTROS GASTOS DEL 997 682 ? 997.582 : | UNKNOWN | unclassified | ER.02 | cmcc_variante |

| 44 | o DIRECCION AVDA, LOS CONQUISTADORES 1700 FOLIO UN | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 45 | (=) MARGEN DE LA EXPLOTACION | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 46 | Inversiones en otras sociedades | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 47 | MAQUINARIA 211376247 43.379.018 227.497:225 | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 48 | ] TELEFONO RED FIA | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 49 | EMBALAJE | UNKNOWN | unclassified | AC.01 | cmcc_variante |

| 50 | a: SOPORTE | UNKNOWN | unclassified | ER.01 | cmcc_variante |

| ... | (192 more) | ... | ... | ... | ... |



## 5. Method Distribution

| Method | Baseline | Candidate | Δ |

|---|---|---|---|

| cmcc_nombre | 0 | 2 | 2 |

| cmcc_variante | 0 | 275 | 275 |

| code | 28 | 26 | -2 |

| dictionary_exact | 14 | 1 | -13 |

| dictionary_fuzzy | 13 | 10 | -3 |

| learning_exact | 46 | 46 | 0 |

| learning_fuzzy | 10 | 10 | 0 |

| unclassified | 445 | 186 | -259 |



## 6. Layout Comparison

| Layout | Baseline Coverage | Candidate Coverage | Δ (pp) |

|---|---|---|---|

| pdf_estandar | 19.96% | 66.55% | 46.59 |



## 7. Concept Impact Analysis

### Concepts that Improve (2)

| Code | Baseline % | Candidate % | Δ (pp) |

|---|---|---|---|

| ER.08 | 0% | 100.0% | +100.0 |

| ER.11 | 0% | 100.0% | +100.0 |



### Concepts that Worsen (0)

*No concepts worsened.*



## 8. Conclusions

- **Coverage:** 34.19% → 34.19% (Δ = +0.0pp)

- **UNKNOWN reduction:** 259 accounts recovered

- **GS Accuracy:** 100.0% → 100.0% (Δ = +0.0000)

- **Changed classifications:** 242 (46.81% of total accounts)

- **Concepts improved:** 2 | **Concepts worsened:** 0

- **Net coverage impact:** +200.0pp concepts improved, -0pp concepts worsened = +200.0pp net



### Verdict: NO SIGNIFICANT CHANGE

CMCC integration shows no measurable improvement.

---

*Generated by `scripts/cmcc_official_benchmark.py`*

*Sources: datasets/*, *gold_standard.db*

*No production code was modified during benchmarking.*
