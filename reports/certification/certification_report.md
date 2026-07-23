# Informe de Certificación — Pipeline de Homologación

**Fecha:** 2026-07-09 19:44

**Holdout:** 20 documentos, 2692 cuentas parseadas, 1083 clasificadas
**Gold Standard:** 103 cuentas cotejadas (89 directas + 14 vía fuzzy)

---

## Métricas globales

| Métrica | Valor |
|---------|-------|
| Accuracy | 100.0% |
| Macro F1 | 1.0 |
| Micro F1 | 1.0 |
| Cohen's Kappa | 1.0 (Almost perfect) |
| Correctas | 103 / 103 |
| Incorrectas | 0 |

## Distribución del clasificador (1083 cuentas clasificadas)

| Método | Cuentas | % del total |
|--------|---------|-------------|
| unclassified | 872 | 80.5% |
| learning_exact | 89 | 8.2% |
| code | 59 | 5.4% |
| dictionary_exact | 30 | 2.8% |
| dictionary_fuzzy | 19 | 1.8% |
| learning_fuzzy | 14 | 1.3% |

## Métricas por etiqueta CMCC

| Label | TP | FP | FN | Precision | Recall | F1 |
|-------|----|----|----|-----------|--------|----|
| AC.01 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| AC.03 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| AC.07 | 4 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ANC.01 | 13 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ANC.03 | 3 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ANC.06 | 1 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ANC.07 | 1 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.01 | 5 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.04 | 19 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.07 | 3 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.09 | 10 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.12 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| ER.14 | 6 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PAT.01 | 12 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PAT.02 | 3 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PAT.03 | 4 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PC.01 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PC.05 | 3 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PC.06 | 4 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PC.07 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |
| PC.08 | 2 | 0 | 0 | 100.00% | 100.00% | 1.0000 |

## Resultados por documento

| Documento | Parseadas | Clasificadas | Cotejadas | Correctas | Accuracy | LC | OC | PC |
|-----------|-----------|-------------|-----------|-----------|----------|----|----|----|
| BALANCE CLASIFICADO AICSA 2019.pdf | 101 | 13 | 2 | 2 | 100% | 35% | 95% | 20% |
| BALANCE ORIGINAL 2014.pdf | 371 | 252 | 18 | 18 | 100% | 25% | 50% | 80% |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | 168 | 67 | 8 | 8 | 100% | 25% | 50% | 50% |
| Balance 2015 - Transp Libardon Ltda.pdf | 117 | 39 | 6 | 6 | 100% | 25% | 50% | 50% |
| Balance 2016 Abad Garcia y Pons.pdf | 133 | 94 | 8 | 8 | 100% | 25% | 50% | 80% |
| Balance 2016 Asturias Ltda .pdf | 101 | 61 | 7 | 7 | 100% | 45% | 50% | 80% |
| Balance 2016 Campomanes S A .pdf | 64 | 34 | 7 | 7 | 100% | 25% | 50% | 80% |
| Balance 2017 - Igesur.pdf | 37 | 18 | 3 | 3 | 100% | 45% | 95% | 50% |
| Balance 2017 - Naviera Orca.pdf | 62 | 19 | 0 | 0 | - | 20% | 95% | 50% |
| Balance Agricola El Comino dic 2018.pdf | 92 | 34 | 5 | 5 | 100% | 25% | 50% | 50% |
| Balance Agricola El Dain Ltda 2011 2012.pdf | 186 | 110 | 13 | 13 | 100% | 65% | 50% | 80% |
| Balance Agricola Santa Amelia dic 2018.pdf | 96 | 28 | 2 | 2 | 100% | 45% | 50% | 30% |
| Balance Capiro 2017-2018.pdf | 120 | 72 | 0 | 0 | - | 20% | 50% | 80% |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | 56 | 16 | 2 | 2 | 100% | 25% | 50% | 30% |
| Balance Exportadora Agua Santa dic 2018.pdf | 78 | 23 | 4 | 4 | 100% | 45% | 50% | 30% |
| Balance General SA JAHUEL 2020 V3.pdf | 214 | 81 | 8 | 8 | 100% | 65% | 95% | 50% |
| Balance Vecchiola Dic_2016.pdf | 39 | 21 | 2 | 2 | 100% | 45% | 50% | 80% |
| Balance Xpovin.pdf | 400 | 14 | 0 | 0 | - | 20% | 95% | - |
| EEFF - 2018 Los Nogales.pdf | 54 | 16 | 1 | 1 | 100% | 45% | 95% | 30% |
| balance general guayacan 2020.pdf | 203 | 71 | 7 | 7 | 100% | 65% | 95% | 50% |

## Notas sobre cobertura

Solo 9.5% de las cuentas clasificadas (103 de 1083) pudieron cotejarse contra el Gold Standard.

Las cuentas sin cotejo son principalmente aquellas cuyos nombres no tienen correspondencia en el Gold Standard (134 entradas conceptuales). El pipeline las clasifica mediante código original, diccionario exacto, diccionario fuzzy, o quedan sin clasificar.

Las cuentas con fuzzy match del LearningEngine se certifican verificando que el `matched_name` en el reason corresponda al código final en el Gold Standard.

**100% de accuracy en cuentas cotejables** — sin errores detectados.

**Conclusión:** Concordancia casi perfecta (κ = 1.0) entre el pipeline y el Gold Standard en las 103 cuentas cotejadas.

---

*Generado por `scripts/run_certification.py` en 210.9s*
*No se usó DATASET_DEV. No se modificó el parser.*
*Fuentes: Holdout (20 PDFs), DocumentAssessment, Gold Standard (134 entradas)*