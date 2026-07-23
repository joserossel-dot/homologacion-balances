# SPRINT 26.2 — Full Repository Shadow Execution

Generado: 2026-07-10 14:33:18 UTC

## 1. Resumen Ejecutivo

| Métrica | Valor |
|---|---|
| Archivos procesados | 205 / 206 |
| Cuentas totales | 32444 |
| Cuentas clasificadas | 11696 |
| Cuentas UNKNOWN | 6160 |
| Shadow hits (score ≥ 0.9) | 0 |
| Recuperaciones (UNKNOWN → CMCC) | 0 |
| Cobertura CMCC (% cuentas con score > 0) | 88.8% |
| Tasa de recuperación | 0.0% |
| Score CMCC promedio | 0.6602 |
| Tiempo procesamiento total | 2064.98s |
| Tiempo pared total | 2065.11s |

## 2. Conflictos Detectados

| Tipo | Cantidad | % del total |
|---|---|---|
| coincide | 3844 | 32.9% |
| recovery | 0 | 0.0% |
| discrepa | 0 | 0.0% |
| ambiguo | 6539 | 55.9% |
| sin_evidencia | 1313 | 11.2% |

## 3. Distribución de Métodos (Línea Base)

| Método | Veces |
|---|---|
| cmcc_nombre | 64 |
| cmcc_variante | 3780 |
| code | 189 |
| dictionary_exact | 3 |
| dictionary_fuzzy | 193 |
| learning_exact | 1138 |
| learning_fuzzy | 169 |
| unclassified | 6160 |

## 4. Top Conceptos Recuperados

| # | Concepto | Veces | % del total |
|---|---|---|---|

## 5. Empresas Más Beneficiadas

| # | Empresa | Recuperaciones | Cuentas Totales | % Recuperación |
|---|---|---|---|---|
| 1 | Soc Com e Inv | 0 | 193 | 0.0% |
| 2 | ORIGINAL | 0 | 504 | 0.0% |
| 3 | Los Nogales | 0 | 62 | 0.0% |
| 4 | Agricola El Comino dic | 0 | 68 | 0.0% |
| 5 | Xpovin | 0 | 28 | 0.0% |
| 6 | Clasificado y Estado resultado | 0 | 32 | 0.0% |
| 7 | Campomanes S A | 0 | 68 | 0.0% |
| 8 | general guayacan | 0 | 142 | 0.0% |
| 9 | Transp Libardon Ltda | 0 | 78 | 0.0% |
| 10 | CLASIFICADO AICSA | 0 | 26 | 0.0% |
| 11 | Asturias Ltda | 0 | 122 | 0.0% |
| 12 | Agricola Santa Amelia dic | 0 | 56 | 0.0% |
| 13 | General SA JAHUEL V3 | 0 | 162 | 0.0% |
| 14 | Naviera Orca | 0 | 38 | 0.0% |
| 15 | Exportadora Agua Santa dic | 0 | 46 | 0.0% |
| 16 | Igesur | 0 | 36 | 0.0% |
| 17 | Vecchiola Dic | 0 | 42 | 0.0% |
| 18 | Abad Garcia y Pons | 0 | 271 | 0.0% |
| 19 | Agricola El Dain Ltda | 0 | 280 | 0.0% |
| 20 | Capiro | 0 | 144 | 0.0% |

## 6. Impacto por Layout

| Layout | Shadow Hits | Cuentas Totales | Recuperadas | % Recup. |
|---|---|---|---|---|

## 7. Distribución de Scores CMCC


## 8. Distribución por Archivo

| # | Archivo | Layout | Cuentas | UNKNOWN | Shadow Hits | Tiempo (s) |
|---|---|---|---|---|---|---|
| 1 | HOLDOUT/Balance 2015 - Soc Com e Inv Campoamor SA.pdf | pdf_estandar | 168 | 25 | 0 | 25.649 |
| 2 | HOLDOUT/BALANCE ORIGINAL 2014.pdf | pdf_estandar | 371 | 104 | 0 | 44.613 |
| 3 | HOLDOUT/EEFF - 2018 Los Nogales.pdf | pdf_estandar | 54 | 1 | 0 | 0.665 |
| 4 | HOLDOUT/Balance Agricola El Comino dic 2018.pdf | pdf_estandar | 92 | 6 | 0 | 17.482 |
| 5 | HOLDOUT/Balance Xpovin.pdf | pdf_estandar | 400 | 14 | 0 | 2.08 |
| 6 | HOLDOUT/Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda | pdf_estandar | 56 | 3 | 0 | 7.892 |
| 7 | HOLDOUT/Balance 2016 Campomanes S A .pdf | pdf_estandar | 64 | 6 | 0 | 9.898 |
| 8 | HOLDOUT/balance general guayacan 2020.pdf | pdf_estandar | 203 | 16 | 0 | 3.88 |
| 9 | HOLDOUT/Balance 2015 - Transp Libardon Ltda.pdf | pdf_estandar | 117 | 11 | 0 | 13.417 |
| 10 | HOLDOUT/BALANCE CLASIFICADO AICSA 2019.pdf | pdf_estandar | 101 | 0 | 0 | 1.116 |
| 11 | HOLDOUT/Balance 2016 Asturias Ltda .pdf | pdf_estandar | 101 | 19 | 0 | 14.327 |
| 12 | HOLDOUT/Balance Agricola Santa Amelia dic 2018.pdf | pdf_estandar | 96 | 5 | 0 | 17.374 |
| 13 | HOLDOUT/Balance General SA JAHUEL 2020 V3.pdf | pdf_estandar | 214 | 36 | 0 | 2.903 |
| 14 | HOLDOUT/Balance 2017 - Naviera Orca.pdf | pdf_estandar | 62 | 15 | 0 | 0.924 |
| 15 | HOLDOUT/Balance Exportadora Agua Santa dic 2018.pdf | pdf_estandar | 78 | 2 | 0 | 14.031 |
| 16 | HOLDOUT/Balance 2017 - Igesur.pdf | pdf_estandar | 37 | 12 | 0 | 0.738 |
| 17 | HOLDOUT/Balance Vecchiola Dic_2016.pdf | pdf_estandar | 39 | 11 | 0 | 8.51 |
| 18 | HOLDOUT/Balance 2016 Abad Garcia y Pons.pdf | pdf_estandar | 133 | 49 | 0 | 16.024 |
| 19 | HOLDOUT/Balance Agricola El Dain Ltda 2011 2012.pdf | pdf_estandar | 186 | 72 | 0 | 21.24 |
| 20 | HOLDOUT/Balance Capiro 2017-2018.pdf | pdf_estandar | 120 | 64 | 0 | 18.326 |
| 21 | edge_cases/Resumen Balance san Osvaldo 2018.xlsx | excel | 9 | 0 | 0 | 0.275 |
| 22 | edge_cases/Balance 2015 - Soc Com e Inv Campoamor SA.pdf | pdf_estandar | 168 | 25 | 0 | 16.468 |
| 23 | edge_cases/BALANCE ORIGINAL 2014.pdf | pdf_estandar | 371 | 104 | 0 | 42.034 |
| 24 | edge_cases/EEFF - 2018 Los Nogales.pdf | pdf_estandar | 54 | 1 | 0 | 0.617 |
| 25 | edge_cases/Balance Agricola El Comino dic 2018.pdf | pdf_estandar | 92 | 6 | 0 | 16.563 |
| 26 | edge_cases/2018 01 15 Balance OPE simplificado.pdf | pdf_estandar | 16 | 6 | 0 | 0.518 |
| 27 | edge_cases/balance tributario dic 2020 agr tuqui.xlsx | tributario | 165 | 0 | 0 | 0.085 |
| 28 | edge_cases/EEFF - 2017 Los Nogales.pdf | pdf_estandar | 54 | 2 | 0 | 0.815 |
| 29 | edge_cases/BALANCE CLASIFICADO 2016, Alto Jardin SA.pdf | pdf_estandar | 48 | 6 | 0 | 9.712 |
| 30 | edge_cases/Balance General Año 2016 firmado.pdf | pdf_estandar | 0 | 0 | 0 | 0.005 |
| 31 | edge_cases/Balance Xpovin.pdf | pdf_estandar | 400 | 14 | 0 | 3.813 |
| 32 | edge_cases/balance CUPM.xlsx | excel | 16 | 0 | 0 | 0.031 |
| 33 | edge_cases/Balance 12_2015.pdf | pdf_estandar | 27 | 13 | 0 | 1.67 |
| 34 | edge_cases/Balance Clasificado 2016.pdf | pdf_estandar | 50 | 6 | 0 | 20.463 |
| 35 | edge_cases/TWG y filial Balance presentación 2020-2019.pdf | pdf_estandar | 79 | 10 | 0 | 1.651 |
| 36 | edge_cases/Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo L | pdf_estandar | 56 | 3 | 0 | 7.492 |
| 37 | edge_cases/EEFF - 2019 El Estero.pdf | pdf_estandar | 54 | 1 | 0 | 0.686 |
| 38 | edge_cases/Balance Agricola El Carmelo dic 2018.pdf | pdf_estandar | 87 | 0 | 0 | 15.177 |
| 39 | edge_cases/Balance 2016 Campomanes S A .pdf | pdf_estandar | 64 | 6 | 0 | 13.81 |
| 40 | edge_cases/TWG y filial Balance presentación 2021-2020.pdf | pdf_estandar | 79 | 10 | 0 | 2.647 |
| 41 | edge_cases/Balance 2015 - Abad Garcia y Pons Ltda.pdf | pdf_estandar | 182 | 39 | 0 | 25.587 |
| 42 | edge_cases/balance general guayacan 2020.pdf | pdf_estandar | 203 | 16 | 0 | 3.302 |
| 43 | edge_cases/Balance 2015 - Transp Libardon Ltda.pdf | pdf_estandar | 117 | 11 | 0 | 12.316 |
| 44 | edge_cases/BALANCE GENERAL AGRICOLA 09.2016.xlsx | excel | 137 | 0 | 0 | 0.046 |
| 45 | edge_cases/ECDS Balance 10-2020 (1).pdf | pdf_estandar | 2716 | 1303 | 0 | 102.782 |
| 46 | edge_cases/BALANCE CLASIFICADO AICSA 2019.pdf | pdf_estandar | 101 | 0 | 0 | 0.977 |
| 47 | edge_cases/Balances tuniche explicacionxlsx.xlsx | excel | 42 | 0 | 0 | 0.06 |
| 48 | edge_cases/Balance y EERR Exportadora Agua Santa  (USD) 31-12-2017 (Firmado).pdf | pdf_estandar | 76 | 4 | 0 | 16.464 |
| 49 | edge_cases/Balance 2016 Asturias Ltda .pdf | pdf_estandar | 101 | 19 | 0 | 14.389 |
| 50 | edge_cases/Balance 2015 - Comercial Asturias Ltda.pdf | pdf_estandar | 159 | 35 | 0 | 19.301 |
| ... | (155 archivos más) | ... | ... | ... | ... | ... |

## 9. Métodos CMCC Utilizados

| Método CMCC | Veces |
|---|---|

## 10. Conclusiones

- CMCC puede recuperar **0 cuentas UNKNOWN** (**0.0%** del total de 6160 UNKNOWN).
- **3844** cuentas donde CMCC coincide con la clasificación actual (11.8%).
- **0** cuentas donde CMCC discrepa con la clasificación actual.
- **6539** casos ambiguos (score > 0 pero < 0.95).
- **1313** cuentas sin evidencia CMCC (score = 0).

---
*La clasificación oficial NO fue modificada. Modo shadow únicamente.*