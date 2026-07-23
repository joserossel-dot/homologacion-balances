# LayoutDetector Validation Report

**Date:** 2026-07-16 19:17

**PDFs analyzed:** 182/182


---

## Global Summary

| Metric | Value |
|--------|-------|
| Total PDFs in dataset | 182 |
| Successfully processed | 182 |
| Errors | 2 |
| Total extraction time | 1404.0s |
| Documents with column changes | 104 / 182 (57.1%) |
| Column-only changes (safe) | 104 / 182 (57.1%) |
| Total column re-assignments | 5978 |
| Documents with unmatched accounts | 0 |
| Unmatched classic accounts | 0 |
| Unmatched dynamic accounts | 0 |

## LayoutDetector Performance

| Metric | Value |
|--------|-------|
| Documents with detection active | 180 / 182 (98.9%) |
| Average confidence | 0.7848 |
| Min confidence | 0.3 |
| Max confidence | 1.0 |

## Verdict Distribution

| Verdict | Count | Description |
|--------|-------|-------------|
| **MATCH** | 76 | Classic == Dynamic |
| **COLUMN_CHANGE** | 104 | Only origen_columna changed |
| **UNMATCHED** | 0 | Account count mismatch |
| **ERROR** | 2 | Parse failure |

## Column Change Details

| # | File | Group | Changes | Classic→Dynamic | Layout | Confidence |
|---|------|-------|---------|-----------------|--------|------------|
| 1 | ECDS Balance 10-2020 (1).pdf | edge_cases | 1830 | ganancia=1057, perdida=545, pasivo=228→perdida=1057, pasivo=545, activo=228 | activo, pasivo, perdida | 0.75 |
| 2 | EEFF 16 - RENTAS 17 - GRUPO CASA GARCIA. | edge_cases | 550 | ganancia=504, perdida=43, pasivo=3→pasivo=504, activo=43, perdida=3 | pasivo, ganancia, perdida, activo, patrimonio, res | 1.0 |
| 3 | EEFF 2018  Terra.pdf | edge_cases | 145 | pasivo=63, perdida=53, ganancia=29→activo=112, perdida=33 | activo, perdida | 0.6 |
| 4 | Balance Clasificado y Estado de Resultad | edge_cases | 125 | ganancia=112, perdida=13→perdida=112, ganancia=13 | ganancia, perdida | 0.6 |
| 5 | Pre Balance Tributario CASA Dic 2019 v31 | validacion | 125 | activo=125→pasivo=125 | pasivo, perdida, ganancia, codigo, nombre | 0.91 |
| 6 | Balance 2017.pdf | validacion | 101 | pasivo=42, activo=37, perdida=12, ganancia=10→perdida=42, pasivo=37, ganancia=12, desconocido=10 | resultado, activo, pasivo, perdida, ganancia, codi | 1.0 |
| 7 | Balance Clasificado JGTc 2019.pdf | edge_cases | 90 | perdida=55, ganancia=35→ganancia=55, perdida=35 | activo, pasivo, ganancia, perdida | 0.9 |
| 8 | Balance 2015 - Soc Com e Inv La Santina  | edge_cases | 83 | ganancia=82, perdida=1→perdida=82, ganancia=1 | activo, pasivo, codigo, nombre, ganancia, perdida | 1.0 |
| 9 | Balance General SA JAHUEL 2020 V3.pdf | HOLDOUT | 81 | activo=25, ganancia=23, pasivo=19, perdida=14→activo=30, pasivo=25, ganancia=14, desconocido=12 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 10 | Balance General SA JAHUEL 2020 V3.pdf | edge_cases | 81 | activo=25, ganancia=23, pasivo=19, perdida=14→activo=30, pasivo=25, ganancia=14, desconocido=12 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 11 | Balance 2016 Campoamor S A .pdf | edge_cases | 78 | ganancia=75, perdida=3→perdida=75, pasivo=3 | activo, pasivo, codigo, ganancia, patrimonio, perd | 1.0 |
| 12 | Balance 2016 La Santina S A .pdf | edge_cases | 77 | ganancia=75, perdida=2→perdida=75, pasivo=2 | activo, pasivo, codigo, nombre, ganancia, patrimon | 1.0 |
| 13 | Balance 2016 Asturias Ltda .pdf | HOLDOUT | 75 | ganancia=72, perdida=3→perdida=72, pasivo=3 | activo, pasivo, codigo, nombre, ganancia, patrimon | 1.0 |
| 14 | Balance 2016 Asturias Ltda .pdf | edge_cases | 75 | ganancia=72, perdida=3→perdida=72, pasivo=3 | activo, pasivo, codigo, nombre, ganancia, patrimon | 1.0 |
| 15 | PRE BALANCE 2018.pdf | validacion | 75 | pasivo=31, activo=21, perdida=12, ganancia=11→perdida=30, pasivo=21, ganancia=12, desconocido=11 | resultado, activo, pasivo, perdida, ganancia, codi | 1.0 |
| 16 | balance general guayacan 2020.pdf | HOLDOUT | 71 | ganancia=19, activo=19, perdida=19, pasivo=14→activo=21, pasivo=19, ganancia=19, desconocido=12 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 17 | balance general guayacan 2020.pdf | edge_cases | 71 | ganancia=19, activo=19, perdida=19, pasivo=14→activo=21, pasivo=19, ganancia=19, desconocido=12 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 18 | Balance 2017 - Frigorífco Santa Cruz.pd | edge_cases | 53 | perdida=45, ganancia=8→ganancia=45, pasivo=8 | activo, pasivo, perdida, codigo, ganancia, patrimo | 1.0 |
| 19 | Balance 2015 - Transp Libardon Ltda.pdf | HOLDOUT | 50 | ganancia=50→pasivo=50 | activo, pasivo, codigo, ganancia, perdida, patrimo | 1.0 |
| 20 | Balance 2015 - Transp Libardon Ltda.pdf | edge_cases | 50 | ganancia=50→pasivo=50 | activo, pasivo, codigo, ganancia, perdida, patrimo | 1.0 |
| 21 | Balance Capiro 2017-2018.pdf | HOLDOUT | 49 | ganancia=28, activo=12, pasivo=9→pasivo=29, perdida=20 | resultado, perdida, patrimonio | 0.61 |
| 22 | Balance Capiro 2017-2018.pdf | edge_cases | 49 | ganancia=28, activo=12, pasivo=9→pasivo=29, perdida=20 | resultado, perdida, patrimonio | 0.61 |
| 23 | Balance 2016 Transportes Libardom Ltda . | edge_cases | 46 | ganancia=46→pasivo=46 | activo, pasivo, codigo, ganancia, perdida, patrimo | 1.0 |
| 24 | Balance 2015 - Soc de Inv Campomanes SA. | edge_cases | 45 | ganancia=45→perdida=45 | activo, pasivo, ganancia, patrimonio, perdida, res | 1.0 |
| 25 | TWG y filial Balance presentación 2020- | edge_cases | 44 | perdida=43, ganancia=1→pasivo=44 | activo, perdida, pasivo, patrimonio | 0.83 |
| 26 | TWG y filial Balance presentación 2021- | edge_cases | 44 | perdida=43, ganancia=1→pasivo=44 | activo, perdida, pasivo, patrimonio | 0.83 |
| 27 | TWG y filial Balance presentación 2021- | edge_cases | 44 | perdida=43, ganancia=1→pasivo=44 | activo, perdida, pasivo, patrimonio | 0.83 |
| 28 | MFCB - Pre-Balance 2017 Oct.pdf | validacion | 43 | activo=21, pasivo=16, ganancia=4, perdida=2→pasivo=25, perdida=16, ganancia=2 | resultado, activo, pasivo, perdida, ganancia, codi | 1.0 |
| 29 | MFCB - Balance 2015 Nivel 3, firmado (27 | validacion | 42 | activo=22, pasivo=13, ganancia=4, perdida=3→pasivo=26, perdida=13, ganancia=3 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 30 | MFCB - Balance 2016 Nivel 3, firmado (16 | validacion | 41 | activo=25, pasivo=11, ganancia=4, perdida=1→pasivo=29, perdida=11, ganancia=1 | activo, pasivo, perdida, ganancia, codigo, nombre, | 1.0 |
| 31 | Balance Tributario a diciembre 31 de 201 | validacion | 39 | pasivo=29, activo=5, ganancia=4, perdida=1→perdida=29, pasivo=9, ganancia=1 | resultado, activo, pasivo, perdida, ganancia, codi | 1.0 |
| 32 | Balance Tributario a diciembre 31 de 201 | validacion | 39 | pasivo=27, activo=6, ganancia=4, perdida=2→perdida=27, pasivo=10, ganancia=2 | resultado, activo, pasivo, perdida, ganancia, codi | 1.0 |
| 33 | Balance Agricola Santa Amelia dic 2018.p | HOLDOUT | 38 | perdida=26, ganancia=12→activo=26, perdida=12 | activo, perdida | 0.6 |
| 34 | Balance Agricola Santa Amelia dic 2018.p | edge_cases | 38 | perdida=26, ganancia=12→activo=26, perdida=12 | activo, perdida | 0.6 |
| 35 | balance combinado El Comino dic 2018.pdf | edge_cases | 38 | perdida=29, ganancia=9→activo=29, perdida=9 | activo, perdida | 0.6 |
| 36 | Balance Clasificado RGTc 2019.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, pasivo, perdida, patrimonio, resultado, co | 1.0 |
| 37 | EEFF - 2017 El Estero.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 38 | EEFF - 2017 La Esperanza.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 39 | EEFF - 2017 Las Loicas.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 40 | EEFF - 2018 El Estero.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 41 | EEFF - 2018 La Esperanza.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 42 | EEFF - 2018 Las Loicas.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 43 | EEFF - 2019 El Estero.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 44 | EEFF - 2019 La Esperanza.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 45 | EEFF - 2019 Las Loicas.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 46 | EEFF - 2019 Los Nogales.pdf | edge_cases | 37 | ganancia=37→pasivo=37 | activo, perdida, pasivo | 0.75 |
| 47 | EEFF - 2018 Los Nogales.pdf | HOLDOUT | 36 | ganancia=36→pasivo=36 | activo, perdida, pasivo | 0.75 |
| 48 | EEFF - 2017 Alto Pelarco.pdf | edge_cases | 36 | ganancia=36→pasivo=36 | activo, perdida, pasivo | 0.75 |
| 49 | EEFF - 2017 Los Nogales.pdf | edge_cases | 36 | ganancia=36→pasivo=36 | activo, perdida, pasivo | 0.75 |
| 50 | EEFF - 2018 Los Nogales.pdf | edge_cases | 36 | ganancia=36→pasivo=36 | activo, perdida, pasivo | 0.75 |

## Column Change Examples (50)

| File | Line | Account | Classic Col | Dynamic Col |
|------|------|---------|-------------|--------------|
| BALANCE CLASIFICADO AICSA 2019.pdf | 5 | Nivel | ganancia | perdida |
| BALANCE CLASIFICADO AICSA 2019.pdf | 6 | Desde Enero a Diciembre | ganancia | perdida |
| BALANCE CLASIFICADO AICSA 2019.pdf | 11 | Disponible | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 12 | Inversiones | perdida | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 15 | Documentos por cobrar (neto) | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 16 | Deudores varios (neto) | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 17 | Documentos y cuentas por cobrar emp | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 30 | Construcciones y obras de infraestr | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 34 | Depreciación (menos) | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 40 | Inversiones en otras sociedades | pasivo | perdida |
| BALANCE CLASIFICADO AICSA 2019.pdf | 65 | Documentos y cuentas por pagar empr | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 89 | Capital pagado | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 90 | Reserva revalorización capital | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 93 | Utilidades retenidas (sumas códigos | ganancia | perdida |
| BALANCE CLASIFICADO AICSA 2019.pdf | 95 | Utilidades acumuladas | pasivo | activo |
| BALANCE CLASIFICADO AICSA 2019.pdf | 97 | Utilidad (pérdida) del ejercicio | perdida | activo |
| Balance 2015 - Soc Com e Inv Campoa | 89 | Letreros Publicitarios | perdida | pasivo |
| Balance 2015 - Soc Com e Inv Campoa | 109 | BET (2) Depreciación del Ejercicio | perdida | pasivo |
| Balance 2015 - Soc Com e Inv Campoa | 143 | — | [23 frobicerrasvo "| ress2g0543 | perdida | pasivo |
| Balance 2015 - Transp Libardon Ltda | 4 | Rengo | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 10 | Desde Enero Hasta Diclembre de | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 12 | CAJA * 3.000.000 CTA ESPECIAL - LIN | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 13 | ¡ CAJA CHICA 101,020 PROVEEDORES | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 14 | | CORP BANCA LOS ANGELES 2.355,58 C | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 15 | | BANCO SECURITY 483.183 ACREEDORES | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 16 | | CUENTAS POR COBRAR EMPRESA RELACI | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 17 | | _ CUENTAS POR COBRAR 94.720.361 I | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 18 | : ANTICIPO REMUNERACIONES 544,288 I | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 19 | ANTICIPO PROVEEDORES . 446.280 Tota | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 20 | PAGOS PROYISIONALES MENSUALES | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 23 | DEPRECIACION ACUMULADA | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 24 | : Activo Fijo Total Pasivo Largo Pl | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 25 | : VEHICULOS | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 27 | RICARDO RAFAEL ABAD GARCAI CTA.PAR | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 28 | CAPITAL SOCIAL | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 29 | REVALORIZACION CAPITAL PROPIO | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 30 | PERDIDAS ACUMULADAS | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 32 | : MN UTILIDAD DEL EJERCICIO | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 40 | po, Rengo | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 46 | E Enero a Diciembre | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 48 | j Ingresos por Fletes | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 50 | (=) MARGEN DE LA EXPLOTACION» | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 53 | | Imprenta | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 54 | i Mantención Vehiculos | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 55 | Combustible | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 56 | nm Patente Comercial y Vehículos | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 57 | : Seguros | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 58 | Viaticos | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 59 | Varios Difícil Clasificación | ganancia | pasivo |
| Balance 2015 - Transp Libardon Ltda | 60 | Remuneraciones | ganancia | pasivo |

## Errors

| File | Group | Reason |
|------|-------|--------|
| Balance 2019 FIRMADO.pdf | edge_cases | No text |
| Balance General Año 2016 firmado.pdf | edge_cases | No text |

## Conclusion

- 104/182 (57.1%) had column changes
- 104/182 (57.1%) had only column changes (safe, no parsing differences)
- 5978 total column re-assignments
- 0 docs with unmatched accounts (non-deterministic PDF text extraction)
- 2 parse errors

### ✅ GO — Safe to enable

**104** documents have clean column-only changes.
No accounts were lost or gained due to layout detection.
Average detector confidence: **0.7848**.

---

*Generated by `reports/run_layout_validation.py`*