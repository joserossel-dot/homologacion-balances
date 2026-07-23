# Análisis de 61 cuentas clasificadas solo por MotorHibridoLocal

**PDFs analizados:** 20
- `datasets/HOLDOUT/BALANCE CLASIFICADO AICSA 2019.pdf`
- `datasets/HOLDOUT/BALANCE ORIGINAL 2014.pdf`
- `datasets/HOLDOUT/Balance 2015 - Soc Com e Inv Campoamor SA.pdf`
- `datasets/HOLDOUT/Balance 2015 - Transp Libardon Ltda.pdf`
- `datasets/HOLDOUT/Balance 2016 Abad Garcia y Pons.pdf`
- `datasets/HOLDOUT/Balance 2016 Asturias Ltda .pdf`
- `datasets/HOLDOUT/Balance 2016 Campomanes S A .pdf`
- `datasets/HOLDOUT/Balance 2017 - Igesur.pdf`
- `datasets/HOLDOUT/Balance 2017 - Naviera Orca.pdf`
- `datasets/HOLDOUT/Balance Agricola El Comino dic 2018.pdf`
- `datasets/HOLDOUT/Balance Agricola El Dain Ltda 2011 2012.pdf`
- `datasets/HOLDOUT/Balance Agricola Santa Amelia dic 2018.pdf`
- `datasets/HOLDOUT/Balance Capiro 2017-2018.pdf`
- `datasets/HOLDOUT/Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf`
- `datasets/HOLDOUT/Balance Exportadora Agua Santa dic 2018.pdf`
- `datasets/HOLDOUT/Balance General SA JAHUEL 2020 V3.pdf`
- `datasets/HOLDOUT/Balance Vecchiola Dic_2016.pdf`
- `datasets/HOLDOUT/Balance Xpovin.pdf`
- `datasets/HOLDOUT/EEFF - 2018 Los Nogales.pdf`
- `datasets/HOLDOUT/balance general guayacan 2020.pdf`

**Total cuentas extraídas:** 1333

## Comparación de clasificación

| Categoría | Cuentas | % del total |
|-----------|---------|-------------|
| Ambos clasifican (mismo código) | 304 | 22.8% |
| Ambos clasifican (código diferente) | 31 | 2.3% |
| Solo LEGACY clasifica | 229 | 17.2% |
| Solo NEW clasifica | 4 | 0.3% |
| Ninguno clasifica | 765 | 57.4% |

## Análisis de 229 cuentas clasificadas solo por LEGACY

### Pareto por mecanismo

| # | Mecanismo | Cuentas | % | % Acumulado |
|---|-----------|---------|---|-------------|
| 1 | regex | 206 | 90.0% | 90.0% |
| 2 | correccion_columna_post | 18 | 7.9% | 97.8% |
| 3 | desambiguacion_columna_pre | 3 | 1.3% | 99.1% |
| 4 | diccionario_fuzzy | 2 | 0.9% | 100.0% |

### Pareto por código regex (dentro de las cuentas solo-LEGACY)

| # | Código estándar | Cuentas | % | % Acumulado |
|---|----------------|---------|---|-------------|
| 1 | AC.01 | 36 | 16.1% | 16.1% |
| 2 | AC.03 | 31 | 13.8% | 29.9% |
| 3 | ANC.01 | 29 | 12.9% | 42.9% |
| 4 | PC.06 | 22 | 9.8% | 52.7% |
| 5 | ER.01 | 19 | 8.5% | 61.2% |
| 6 | PAT.01 | 13 | 5.8% | 67.0% |
| 7 | ANC.03 | 8 | 3.6% | 70.5% |
| 8 | ER.09 | 7 | 3.1% | 73.7% |
| 9 | AC.07 | 6 | 2.7% | 76.3% |
| 10 | ER.14 | 6 | 2.7% | 79.0% |
| 11 | PAT.04 | 6 | 2.7% | 81.7% |
| 12 | AC.05 | 5 | 2.2% | 83.9% |
| 13 | ER.04 | 5 | 2.2% | 86.2% |
| 14 | PC.03 | 5 | 2.2% | 88.4% |
| 15 | PC.01 | 4 | 1.8% | 90.2% |
| 16 | PC.05 | 4 | 1.8% | 92.0% |
| 17 | PNC.03 | 3 | 1.3% | 93.3% |
| 18 | ER.02 | 3 | 1.3% | 94.6% |
| 19 | PC.08 | 2 | 0.9% | 95.5% |
| 20 | ER.10 | 2 | 0.9% | 96.4% |
| 21 | AC.02 | 2 | 0.9% | 97.3% |
| 22 | ER.11 | 2 | 0.9% | 98.2% |
| 23 | AC.04 | 1 | 0.4% | 98.7% |
| 24 | PAT.02 | 1 | 0.4% | 99.1% |
| 25 | PAT.03 | 1 | 0.4% | 99.6% |
| 26 | ER.12 | 1 | 0.4% | 100.0% |

### Pareto por patrón regex específico (dentro de las cuentas solo-LEGACY)

| # | Patrón regex | Código | Cuentas | % | % Acumulado |
|---|--------------|--------|---------|---|-------------|
| 1 | `AC.01(\b(caja\s*chica|caja\s*y\s*ban...)` | AC.01 | 39 | 17.4% | 17.4% |
| 2 | `AC.03(\b(clientes?|deudore(s)?\s*por...)` | AC.03 | 35 | 15.6% | 33.0% |
| 3 | `ANC.01(\b(activo\s*fijo|propiedad(es)...)` | ANC.01 | 29 | 12.9% | 46.0% |
| 4 | `PC.06(\b(remuneracion(es)?|sueldo(s)...)` | PC.06 | 26 | 11.6% | 57.6% |
| 5 | `PAT.01(\b(capital\s*(pagado|suscrito|...)` | PAT.01 | 13 | 5.8% | 63.4% |
| 6 | `ER.01(\b(venta(s)?|ingreso(s)?\s*(po...)` | ER.01 | 12 | 5.4% | 68.8% |
| 7 | `AC.07(\b(iva\s*(credito|cf)|ppm|impu...)` | AC.07 | 11 | 4.9% | 73.7% |
| 8 | `ANC.03(\b(intangible(s)?|goodwill|mar...)` | ANC.03 | 8 | 3.6% | 77.2% |
| 9 | `PC.03(\bleasing\s*(cp|corriente|cort...)` | PC.03 | 7 | 3.1% | 80.4% |
| 10 | `PAT.04(\butilidad\s*del\s*(ejercicio|...)` | PAT.04 | 6 | 2.7% | 83.0% |
| 11 | `ER.09(\bgasto(s)?\s*financiero(s)?|i...)` | ER.09 | 5 | 2.2% | 85.3% |
| 12 | `AC.05(\b(inventario(s)?|existencia(s...)` | AC.05 | 5 | 2.2% | 87.5% |
| 13 | `PC.01(\b(proveedor(es)?|acreedore(s)...)` | PC.01 | 4 | 1.8% | 89.3% |
| 14 | `PC.05(\b(iva\s*(debito|df)|impuesto(...)` | PC.05 | 4 | 1.8% | 91.1% |
| 15 | `PNC.03(\b(bono(s)?|debenture(s)?)\b...)` | PNC.03 | 3 | 1.3% | 92.4% |
| 16 | `ER.02(\bcosto(s)?\s*(de\s*)?(venta(s...)` | ER.02 | 3 | 1.3% | 93.8% |
| 17 | `ER.04(\bgasto(s)?\s*(de\s*)?(adminis...)` | ER.04 | 3 | 1.3% | 95.1% |
| 18 | `PC.08(\b(anticipo(s)?\s*de\s*cliente...)` | PC.08 | 2 | 0.9% | 96.0% |
| 19 | `ER.10(\bimpuesto\s*(a\s*la\s*renta|p...)` | ER.10 | 2 | 0.9% | 96.9% |
| 20 | `AC.02(\b(inversion(es)?\s*(corto\s*p...)` | AC.02 | 2 | 0.9% | 97.8% |
| 21 | `ER.11(\butilidad\s*neta|resultado\s*...)` | ER.11 | 2 | 0.9% | 98.7% |
| 22 | `AC.04(\b(documento(s)?\s*por\s*cobra...)` | AC.04 | 1 | 0.4% | 99.1% |
| 23 | `PAT.02(\b(reserva(s)?(\s*legal)?|prim...)` | PAT.02 | 1 | 0.4% | 99.6% |
| 24 | `PAT.03(\b(utilidad(es)?\s*(acumulada(...)` | PAT.03 | 1 | 0.4% | 100.0% |

### Distribución de confianza (cuentas solo-LEGACY)

| Rango | Cuentas | % |
|-------|---------|---|
| 0.95-1.00 | 9 | 3.9% |
| 0.85-0.95 | 220 | 96.1% |
| 0.70-0.85 | 0 | 0.0% |
| < 0.70 | 0 | 0.0% |

## Listado detallado de cuentas clasificadas solo por LEGACY

| PDF | Nombre | Código Raw | Monto | Columna | Código LEGACY | Método LEGACY | Confianza |
|-----|--------|-----------|-------|---------|---------------|--------------|----------|
| BALANCE CLASIFICADO AICSA 2019.pdf | Disponible |  | 385,070 | pasivo | AC.01 | regla_regex | 0.90 |
| BALANCE CLASIFICADO AICSA 2019.pdf | Documentos por cobrar (neto) |  | 376,082 | pasivo | AC.04 | regla_regex | 0.92 |
| BALANCE CLASIFICADO AICSA 2019.pdf | Deudores varios (neto) |  | 987,346 | pasivo | AC.07 | regla_regex | 0.88 |
| BALANCE CLASIFICADO AICSA 2019.pdf | Documentos y cuentas por cobrar empresas relacionadas |  | 1,107,294 | pasivo | AC.03 | regla_regex | 0.90 |
| BALANCE CLASIFICADO AICSA 2019.pdf | Construcciones y obras de infraestructura |  | 27,154 | pasivo | ANC.01 | regla_regex | 0.90 |
| BALANCE CLASIFICADO AICSA 2019.pdf | Reserva revalorización capital |  | 664,968 | pasivo | PAT.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | BANCO CHILE |  | 5,738,675,712 | activo | AC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o BANCO CHILEDOLAR — |  | 3,040,403,927 | activo | AC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | GTA. CTE CLIENTES “RO18.047.831 — |  | 5,628,636,667 | pasivo | AC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | e ANTICIPO PROVEEDORES 1.348.569.258 —1077.117.567 |  | 271,451,691 | perdida | PC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | IVA CREDITO FISCAL 693.484.738 676833294 N |  | 16,651,454 | perdida | AC.07 | regla_regex | 0.88 |
| BALANCE ORIGINAL 2014.pdf | PPM |  | 77,419,044 | pasivo | AC.07 | regla_regex | 0.88 |
| BALANCE ORIGINAL 2014.pdf | MAQUINARIA 211376247 43.379.018 227.497:225 |  | 227 | perdida | ANC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o VEHICULOS |  | 72,245,017 | activo | ANC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o: BANCO CHILE US1 |  | 625,274,400 | activo | AC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | : PROVEEDORES 3776402807 — |  | 4,281,395,062 | pasivo | PC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o. ANTÍCIFO CLIENTE 245053396 — |  | 245,187,391 | pasivo | AC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | AFP |  | 138,334,446 | activo | PC.06 | regla_regex | 0.86 |
| BALANCE ORIGINAL 2014.pdf | a CAJA DECOMPENSACION — |  | 21,440,598 | activo | AC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o IVA DEBITO FISCAL 1094475.077 — |  | 1,281,407,091 | pasivo | PC.05 | regla_regex | 0.88 |
| BALANCE ORIGINAL 2014.pdf | : BANCO CHILE |  | 169,390,000 | pasivo | AC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | E GRATIFICACION |  | 162,348,126 | pasivo | PC.06 | regla_regex | 0.86 |
| BALANCE ORIGINAL 2014.pdf | BONOS |  | 277,173,032 | activo | PNC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | : MAQUINARIA 579.394.650 1.698.296 — |  | 578,196,354 | perdida | ANC.01 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | PATENTES “2301974 |  | 2,301,974 | perdida | ANC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | o LICENCIAS |  | 641,791 | activo | ANC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | COSTO VENTA FRUTA |  | 262,540,030 | activo | ER.02 | regla_regex | 0.92 |
| BALANCE ORIGINAL 2014.pdf | 0 COSTO VENTA ACTIVO |  | 1,500,564 | pasivo | ER.02 | regla_regex | 0.92 |
| BALANCE ORIGINAL 2014.pdf | INDEMNIZACION |  | 3,536,520 | pasivo | PC.06 | regla_regex | 0.86 |
| BALANCE ORIGINAL 2014.pdf | , REMUNERACIONES 122.629.043 122.529.043 i |  | 122,629,043 | ganancia | PC.06 | regla_regex | 0.86 |
| BALANCE ORIGINAL 2014.pdf | hd : GRATIFICACION |  | 10,382,540 | pasivo | PC.06 | regla_regex | 0.86 |
| BALANCE ORIGINAL 2014.pdf | BONOS + |  | 8,363,000 | pasivo | PNC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | l PATENTES |  | 2,561,239 | pasivo | ANC.03 | regla_regex | 0.90 |
| BALANCE ORIGINAL 2014.pdf | OTRAS VENTAS |  | 44,385,938 | pasivo | ER.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | CAJA 5.519,080 PROVEEDORES |  | 3,685,781 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | CAJA CHICA 100.000 CUENTAS POR PAGAR EMPRESA RELACION |  | 392,460,992 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | BANCO CORPBANCA CTA. 2 . 1,495,155 CTA CTE CONSIGNADOR |  | 370 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | BANCO CORPBANCA 5.079.420 CUENTAS POR PAGAR |  | 145,403,729 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | SCOTIABANK 223.810 ACREEDORES VARIOS |  | 2,003,605 | ganancia | PC.08 | regla_regex | 0.85 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | mk TARJETA DIN-ABC 1,197,005 HONORARIOS POR PAGAR |  | 620 | ganancia | ER.01 | regla_regex+columna | 0.91 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | TARJETA DE CREDITO 756.630 IVA DEBITO FISCAL, |  | 15,723,116 | ganancia | PC.05 | regla_regex | 0.88 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | ANTICIPO REMUNERACIONES 1.025.745 Total Pasivo Largo Plazo |  | 132,219,649 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | Activo Fijo s Total PATRIMONIO |  | 78,309 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | Patente Comercial y Vehículos |  | 630 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | Reajuste PPM-IVA |  | 241,569 | ganancia | ER.14 | regla_regex+columna | 0.93 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | Intereses Pagados o Adeudados |  | -5,714,616 | ganancia | ER.09 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | pe Impuesto a la Renta y |  | -1,732,430 | ganancia | ER.10 | regla_regex | 0.90 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | pao [ooo rosso 0) / Mora celo AFP | 17o54azolazo Percesación Pinedo arado |  | 6,262,968 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance 2015 - Transp Libardon Ltda.pdf | ¡ CAJA CHICA 101,020 PROVEEDORES |  | 434 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | | BANCO SECURITY 483.183 ACREEDORES VARIOS |  | 52 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | | _ CUENTAS POR COBRAR 94.720.361 INSTITUCIONES DE PREVISION |  | 1,318,540 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | : ANTICIPO REMUNERACIONES 544,288 IVA DEBITO FISCAL |  | 737,499 | ganancia | PC.05 | regla_regex | 0.88 |
| Balance 2015 - Transp Libardon Ltda.pdf | : Activo Fijo Total Pasivo Largo Plazo |  | 226,228,600 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | i Mantención Vehiculos |  | 3,230,311 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | nm Patente Comercial y Vehículos |  | 187,225 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2015 - Transp Libardon Ltda.pdf | Arriendo por Leasing |  | 3,959,091 | ganancia | ER.01 | regla_regex+columna | 0.95 |
| Balance 2015 - Transp Libardon Ltda.pdf | Reajuste PPM-IVA |  | 17 | ganancia | ER.14 | regla_regex+columna | 0.93 |
| Balance 2016 Abad Garcia y Pons.pdf | CAJA 15.459.392 CARTAS DE CREDITO Y CONFIRMING |  | 99,043,122 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | CAJA CHICA 120.000 CTA ESPECIAL - LINEA DE CREDITO |  | 89,839,933 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | BANCO CORPBANCA CTA.2 3.838.843 PRESTAMOS BANCO SANTANDER |  | 70,344,488 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | BANCO CREDITO E INVERSIONES 60.421 CTA ESPECIAL - LINEA CREDITO BCI |  | 10,198,769 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | BANCO SANTANDER 85.951 PRESTAMO BANCO CREDITO E INVERSIONE |  | 241,410 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | BANCO DE CHILE 1.628.846 PROVEEDORES |  | 1,501 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | BANCO CORPBANCA 1 27.623.350 CUENTAS POR PAGAR EMP. RELAC |  | 972,655,293 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | CLIENTES 161.827.893 PROVEEDORES POR REGULARIZAR |  | 28,277,579 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | TARJETA DE DEBITO 12.501.289 ACREEDORES VARIOS |  | 10,542,046 | ganancia | PC.08 | regla_regex | 0.85 |
| Balance 2016 Abad Garcia y Pons.pdf | CUENTAS POR COBRAR EMP, RELAC., 524.415.304 SUELDOS POR PAGAR |  | 36,496,990 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | CUENTAS POR COBRAR 1.849.279.201 INSTITUCIONES DE PREVISION |  | 16,588,351 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | CUENTAS POR COBRAR ASTURIAS 41.816.067 COMISIONES POR PAGAR |  | 214,823 | ganancia | ER.01 | regla_regex+columna | 0.95 |
| Balance 2016 Abad Garcia y Pons.pdf | DOCUMENTOS PROTESTADOS 44.835,225 HONORARIOS POR PAGAR |  | 4,891,879 | ganancia | ER.01 | regla_regex+columna | 0.91 |
| Balance 2016 Abad Garcia y Pons.pdf | MERCADERIAS 1.012.655.946 RETENCION 2? CATEGORIA |  | 2,666,687 | ganancia | AC.05 | regla_regex | 0.92 |
| Balance 2016 Abad Garcia y Pons.pdf | MERCADERIAS IMPORTADAS 173.670.519 PROVISION IMPTO, 1? CAT |  | 104 | ganancia | AC.05 | regla_regex | 0.92 |
| Balance 2016 Abad Garcia y Pons.pdf | ANTICIPO REMUNERACIONES 7.664.220 Total Pasivo Circulante |  | 6,094,759 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance 2016 Abad Garcia y Pons.pdf | PAGOS PROVISIONALES MENSUALES 114.110.864 PRESTAMO BANCO CORPBANCA |  | 1,329,360 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | IVA CREDITO FISCAL 15.005.038 Pasivo Largo Plazo |  | 1,757,940 | ganancia | AC.07 | regla_regex | 0.88 |
| Balance 2016 Abad Garcia y Pons.pdf | Activo Fijo MARIA DOL. PONS GARCIA, CTA. PART |  | 56,315,874 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | TERRENOS 359.764.996 CAPITAL SOCIAL |  | 2,420,640 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | EDIFICIOS 1.433.522.339 REV, CAPITAL PROPIO |  | 611,281,208 | ganancia | PAT.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | MUEBLES Y UTILES 48.145.076 Total Patrimonio |  | 590,593,066 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | SOFTWARE |  | 35,849,123 | ganancia | ANC.03 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | INSTALACIONES 39.578.745 UTILIDAD DEL EJERCICIO |  | 328,924,054 | ganancia | PAT.04 | regla_regex | 0.92 |
| Balance 2016 Abad Garcia y Pons.pdf | DEPOSITO A PLAZO EN US$ |  | 237,883,249 | ganancia | AC.02 | regla_regex | 0.92 |
| Balance 2016 Abad Garcia y Pons.pdf | Mantención Edificio y Vehículos |  | 18,680,809 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | Patente Comercial y Vehículos |  | 4,487,149 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | Mantención Activo Fijo |  | 180,937 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | Gastos por Software y Soporte Técnico |  | 7,246,371 | ganancia | ANC.03 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | Comisiones |  | 99,268,698 | ganancia | ER.01 | columna_ambiguo | 0.88 |
| Balance 2016 Abad Garcia y Pons.pdf | Arriendos por Leasing |  | 16,859,300 | ganancia | ER.01 | regla_regex+columna | 0.95 |
| Balance 2016 Abad Garcia y Pons.pdf | Reajuste PPM-IVA |  | 3,464,736 | ganancia | ER.14 | regla_regex+columna | 0.93 |
| Balance 2016 Abad Garcia y Pons.pdf | Otras Ventas Fuera del Giro |  | 7,122,828 | ganancia | ER.01 | regla_regex | 0.90 |
| Balance 2016 Abad Garcia y Pons.pdf | Intereses Pagados o Adeudados |  | -123,769,292 | ganancia | ER.09 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | Al 31 de Diciembre de |  | 2,016 | ganancia | __EXCLUIR__ | diccionario_fuzzy | 0.88 |
| Balance 2016 Asturias Ltda .pdf | CAJA 360.000 PROVEEDORES |  | 5,361,491 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | CAJA CHICA 100.000 CUENTAS POR PAGAR EMPRESA RELAC |  | 772,867,305 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | BANCO CORPBANCA CUENTA 2 703.963 CTA CTE CONSIGNADOR |  | 476,545,331 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | BANCO DE CHILE 388.713 DOCUMENTOS A FECHA POR PAGAR |  | 1,121,300 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | BANCO CORPBANCA 1 609.590 CUENTAS POR PAGAR PONS |  | 41,816,067 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | CLIENTES 10.472.340 ACREEDORES VARIOS |  | 5,764,873 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | TARJETA DIN-ABC 379.332 SUELDOS POR PAGAR |  | 8,473,070 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance 2016 Asturias Ltda .pdf | CUENTAS POR COBRAR EMPRESA RELAC. 785.538.275 HONORARIOS POR PAGAR |  | 137,000 | ganancia | ER.01 | regla_regex+columna | 0.95 |
| Balance 2016 Asturias Ltda .pdf | CUENTAS POR COBRAR 710.453.558 IVA DEBITO FISCAL |  | 31,109,273 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | MERCADERIAS 73.252.176 Total Pasivo Circulante |  | 2,138,617,995 | ganancia | AC.05 | regla_regex | 0.92 |
| Balance 2016 Asturias Ltda .pdf | Activo Fijo REVALORIZACION CAPITAL PROPIO |  | 21,371,390 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | MUEBLES Y UTILES 5.029.595 PERDIDAS ACUMULADAS |  | -262,753,237 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | Mantención Edificio y Vehículos |  | 1,133,891 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | Patente Comercial y Vehículos |  | 429,426 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | Gastos por Software y Soporte Tecnico |  | 495,434 | ganancia | ANC.03 | regla_regex | 0.90 |
| Balance 2016 Asturias Ltda .pdf | Comisiones |  | 14,072,217 | ganancia | ER.01 | columna_ambiguo | 0.88 |
| Balance 2016 Asturias Ltda .pdf | Reajuste PPM-IVA |  | 670,742 | ganancia | ER.14 | regla_regex+columna | 0.93 |
| Balance 2016 Asturias Ltda .pdf | Intereses Pagados o Adeudados |  | -27,579 | ganancia | ER.09 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | Al 31 de Diciembre de |  | 2,016 | ganancia | __EXCLUIR__ | diccionario_fuzzy | 0.88 |
| Balance 2016 Campomanes S A .pdf | CAJA 189.933 PROVEEDORES |  | 634,249 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | BANCO BICE 706.171 DOCUMENTOS POR PAGAR |  | 8,855,968 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | CLIENTES CAMPOMANES 71.271.257 CUENTAS POR PAGAR |  | 1,688,787,679 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | CLIENTES CASA GARCIA 748.339.585 ACREEDORES VARIOS |  | 816,843 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | CLIENTES ASTURIAS 119.042.734 SUELDOS POR PAGAR |  | 6,989,198 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | CLIENTES CAMPOAMOR 98.198.704 INSTITUCIONES DE PREVISION |  | 1,750,504 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | CLIENTES LA SANTINA 16.868.570 HONORARIOS POR PAGAR |  | 94,328 | ganancia | ER.01 | regla_regex+columna | 0.95 |
| Balance 2016 Campomanes S A .pdf | CUENTAS POR COBRAR 435.225.144 RETENCION 2? CATEGORIA |  | 162,526 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | ANTICIPO REMUNERACIONES 963.378 Pasivo Circulante |  | 1,708,095,697 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance 2016 Campomanes S A .pdf | RESERVA REVALORIZ. CAPITAL PROPIO |  | 36,423,640 | ganancia | PAT.01 | regla_regex | 0.90 |
| Balance 2016 Campomanes S A .pdf | Recuperacion Gastos de Administracion |  | 33,075,784 | ganancia | ER.04 | regla_regex | 0.88 |
| Balance 2016 Campomanes S A .pdf | Comisiones |  | 13,538,254 | ganancia | ER.01 | columna_ambiguo | 0.88 |
| Balance 2016 Campomanes S A .pdf | Reajuste PPM-IVA |  | 38,413 | ganancia | ER.14 | regla_regex+columna | 0.93 |
| Balance 2017 - Igesur.pdf | Banco CLP 1.793.428 Ctas por pagar |  | 2,811,812 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2017 - Igesur.pdf | Banco USD 574.607 Ptmos Bancarios |  | 35,000,000 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance 2017 - Igesur.pdf | Clientes 2.425.570 Impuestos por pagar |  | 281,181 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance 2017 - Igesur.pdf | Impuestos por Recuperar 21.711.381 Cta Cte relacionadas |  | 12,539,506 | ganancia | AC.07 | regla_regex | 0.88 |
| Balance 2017 - Igesur.pdf | Terrenos 80.024.366 Capital |  | 2,000,000 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance 2017 - Igesur.pdf | Pozo 37.760.334 Rev. Capital Propio |  | 11,347,652 | ganancia | PAT.01 | regla_regex | 0.90 |
| Balance 2017 - Igesur.pdf | Piscicultura 113.293.296 Otras Reservas |  | 674,120,521 | ganancia | PAT.02 | regla_regex | 0.88 |
| Balance 2017 - Igesur.pdf | Inversiones en Empresas 1.668.792.488 Resultados Acumulados |  | 1,064,698,027 | ganancia | PAT.03 | regla_regex | 0.90 |
| Balance 2017 - Naviera Orca.pdf | VESSELS AND MACHINERIES 31.634.183 35.015.073 PAID CAPITAL |  | 1,489,580 | perdida | PAT.01 | regla_regex | 0.90 |
| Balance 2017 - Naviera Orca.pdf | NET INCOME FOR THE PERIOD |  | 2,206,664 | perdida | ER.11 | regla_regex | 0.92 |
| Balance 2017 - Naviera Orca.pdf | TAX ASSETS, CURRENT 16.603 11.373 LEASING PAYABLES |  | 27,259 | perdida | PC.03 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Disponible |  | 20,339,296 | perdida | AC.01 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Deudores por venta USD O] |  | 1,133,030,356 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Documentos y cuentas por cobrar a empresas |  | 34,596,324 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Construcciones y obras de infraestructura |  | 1,302,443,997 | perdida | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Documentos y cuentas por cobrar empresas |  | 1,755,493,152 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Obligaciones por leasing largo plazo |  | 227,153,260 | perdida | PC.03 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Reservas revalorización capital |  | 32,066,737 | perdida | PAT.01 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | GASTOS DE ADMINISTRACIÓN Y VENTA |  | -459,281,434 | perdida | ER.01 | regla_regex | 0.90 |
| Balance Agricola El Comino dic 2018.pdf | Utilidad (pérdida) en venta de activo fijo |  | 1,008,403 | ganancia | PAT.04 | regla_regex | 0.92 |
| Balance Agricola El Comino dic 2018.pdf | Utilidad (Pérdida) / Ingresos Explotac..(Y%) |  | 14 | ganancia | PAT.04 | regla_regex | 0.92 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | GASTOS REAJUSTE BANCO 605156 a 5605156 a a a |  | 5,685,156 | ganancia | ER.14 | regla_regex+columna | 0.95 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | IMPUESTO RENTA 12 CATG. 539466 B 539466 a Li] a |  | 539,466 | ganancia | PC.05 | regla_regex | 0.88 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | INTERES BANCO 17065433 a 17065433 g |  | 8 | perdida | ER.09 | regla_regex+columna | 0.95 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | SUELDOS 34104489 a 34194489 a |  | 34,194,489 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VACACIONES PROPORCIONALES 981749 a 981749 a |  | 981,748 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | CAJA 1114973895 1892390382 22582793 a |  | 22,582,793 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | CONSTRUCCION POZO 8483361 a 8483361 a |  | 8,403,361 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | MUEBLES Y UTILES 296407 217069 69347 69347 a |  | 3 | perdida | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VEHICULO 1995849 365283 730566 B 730566 E] |  | 5 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | SUELDOS POR PAGAR 20043341 292202 a 876661 B |  | 876,661 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | GASTOS GENERALES 19315181 8 19315181 B g a |  | 19,315,181 | ganancia | ER.04 | regla_regex | 0.88 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | CAJA |  | 114,698,208 | activo | AC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | CONSTRUCCION POZO |  | 29,333,096 | activo | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | EQUIPO COMPUTACION |  | 202,071 | activo | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | ANTICIPO SUELDOS |  | 0 | activo | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | GASTOS VEHICULOS |  | 506,815 | perdida | ANC.01 | regla_regex | 0.90 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | INTERESES BANCO |  | 26,009,941 | perdida | ER.09 | regla_regex+columna | 0.95 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | SUELDOS |  | 39,547,340 | perdida | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VACACIONES PROPORCIONALES |  | 206,763 | perdida | PC.06 | regla_regex | 0.86 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VENTAS EXENTAS |  | 6,300,000 | ganancia | ER.01 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Disponible |  | 9,590,174 | perdida | AC.01 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Deudores por venta (neto) |  | 140,985,265 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Deudores por venta USD |  | 67,655,674 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Documentos y cuentas por cobrar a empresas |  | 153,803 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Construcciones y obras de infraestructura |  | 999,540,899 | perdida | ANC.01 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Documentos y cuentas por cobrar a empresas |  | 1,361,467,745 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | GASTOS DE ADMINISTRACIÓN Y VENTA |  | -430,520,604 | perdida | ER.01 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Utilidad (pérdida) en venta de activo fijo |  | 19,504,882 | perdida | PAT.04 | regla_regex | 0.92 |
| Balance Agricola Santa Amelia dic 2018.pdf | | Impuestoalarenta |  | -19,683,367 | ganancia | ER.10 | regla_regex | 0.90 |
| Balance Agricola Santa Amelia dic 2018.pdf | Utilidad (Pérdida) / Ingresos Explotac..(%) (16.57%) |  | 11 | ganancia | PAT.04 | regla_regex | 0.92 |
| Balance Capiro 2017-2018.pdf | 1101-51 CAVA O BANCO 5.719.311.107] 4.860.238.854 839.072.253 0 859.072.253 Q |  | 0 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 1303-01 DEUDORES CLIENTES 6.595.633.636| |  | 417,350,600 | activo | AC.03 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 2106-D1 SUELDOS POR PAGAR 50.874.211 54.092.493 ? |  | 6 | activo | PC.06 | regla_regex | 0.86 |
| Balance Capiro 2017-2018.pdf | 2106-03 HONORARIOS POR PAGAR 35.200.000 39.760.000 y |  | 4,560,000 | pasivo | ER.04 | regla_regex+columna | 0.91 |
| Balance Capiro 2017-2018.pdf | 2201-01 CAPITAL SOCIAL |  | 5,000,000 | pasivo | PAT.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 2201-02 RESERVA REV, CAPITAL |  | 479,997 | pasivo | PAT.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 4102-01 REMUNERACIONES 51.149.664 0 51.149.664 0 0 : |  | 51,149,664 | perdida | PC.06 | regla_regex | 0.86 |
| Balance Capiro 2017-2018.pdf | 5101-01 INGRESOS POR VENTAS 206.706.664] 4.784,599.727 0| 3.577.893.063 o 0 O] |  | 4,577,893,063 | ganancia | ER.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 1303-07 DEUDORES CLIENTES 5.921.148.2069 5.239.832.052 681.316.016 e £81.318.016 |  | 6 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 1404-82 IVA CREDITO FISCAL 288,637.367 288.637.367 ú < 0 a |  | 0 | ganancia | AC.07 | regla_regex | 0.88 |
| Balance Capiro 2017-2018.pdf | 2301-03 PROVEEDORES 5.295.438.712] 5.928.781.12% S |  | 633,343,013 | pasivo | PC.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 2106-01 SUELDOS” POR PAGAR 11.777.905 15.962.042 0 4.185.037 0 4.185.037 D |  | 0 | ganancia | PC.06 | regla_regex | 0.86 |
| Balance Capiro 2017-2018.pdf | 2106-03 HONORARIOS POR PAGAR 34.529.500 36.529.500 9 2.000.008 : |  | 2,000,000 | pasivo | ER.04 | regla_regex+columna | 0.91 |
| Balance Capiro 2017-2018.pdf | 2201-01 CAPITAL SOCIAL E] |  | 5,000,000 | pasivo | PAT.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 2261-92 RESERVA REV: CAPITAL p 479.297 o : |  | 9 | activo | PAT.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | 4101-01 COSTOS DE VENTAS 3.193.290 .742 3.633.123 2.188.657.621 0 0 . Oj |  | 3,188,657,621 | perdida | ER.02 | regla_regex | 0.92 |
| Balance Capiro 2017-2018.pdf | | 4201-91 CM, CAPITAL PROPTG 439,997 o 439.997 A |  | 432,297 | ganancia | PAT.01 | regla_regex | 0.90 |
| Balance Capiro 2017-2018.pdf | SI01-01 INGRESOS POM VENTAS 352.268.137) 3.927.888.42] 617 3.574,920.284 El |  | 21 | perdida | ER.01 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Disponible 44,525,571 Documentos por pagar |  | 788,004 | ganancia | AC.01 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Anticipo Proveedores 53,414 Retenciones |  | 4,488,506 | ganancia | PC.01 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Bono |  | 29,956,171 | ganancia | PNC.03 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Activo Fijo 295,765,566 Cuanta por pagar inversiones Imperator |  | 332,635 | ganancia | ANC.01 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Gastos de administración y ventas |  | -376,916,874 | ganancia | ER.01 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Gastos financieros (menos) |  | 0 | ganancia | ER.09 | regla_regex | 0.90 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | Utilidad (perdida) liquida |  | -379,458,280 | ganancia | PAT.04 | regla_regex | 0.92 |
| Balance Exportadora Agua Santa dic 2018.pdf | Disponible |  | 172,978 | perdida | AC.01 | regla_regex | 0.90 |
| Balance Exportadora Agua Santa dic 2018.pdf | Deudores por venta (neto) |  | 3,517,097 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Exportadora Agua Santa dic 2018.pdf | Documentos y cuentas por cobrar empresas |  | 8,661 | perdida | AC.03 | regla_regex | 0.90 |
| Balance Exportadora Agua Santa dic 2018.pdf | GASTOS DE ADMINISTRACIÓN Y VENTA |  | 2,009,250 | ganancia | ER.01 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Provisión Intereses Bancarios | 2111008 | 4,158,789 | pasivo | ER.09 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Obligaciones por Leasing LP porción CP CLP | 2111011 | 157,219,695 | pasivo | PC.03 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Provisione de Vacaciones | 2116001 | 2,446,507 | pasivo | PC.06 | regla_regex | 0.86 |
| Balance General SA JAHUEL 2020 V3.pdf | Obligaciones por Leasing LP CLP | 2121003 | 786,098,475 | pasivo | PC.03 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Impto. Dif. por Leasing | 2125007 | 564,544,274 | pasivo | PC.03 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | GASTOS DE ADMINISTRACION Y VENTA | 3120000 | — | desconocido | ER.01 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Remuneraciones Adm. y Venta | 3125001 | 15,057,096 | perdida | ER.01 | regla_regex | 0.90 |
| Balance General SA JAHUEL 2020 V3.pdf | Ingresos por Mediciones de Fondos Mutuos | 4121002 | 26,673 | ganancia | AC.02 | regla_regex | 0.92 |
| Balance Vecchiola Dic_2016.pdf | Deudores Comerciales y Otras Cuentas por Cobrar 20.394,861,653 Acreedores Comerciales y Otras Cuentas por Pagar |  | 4,654 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Vecchiola Dic_2016.pdf | Cuentas por cobrar a entidades relacionadas 5.163.998.112 Cuentas por Pagar a Entidades Relacionadas |  | 935,747,309 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Vecchiola Dic_2016.pdf | Inventarios 309.739.893 Provisiones por beneficios a los empleados, corrientes |  | 961,821,614 | ganancia | AC.05 | regla_regex | 0.92 |
| Balance Vecchiola Dic_2016.pdf | Deudores Comerciales y Otras Cuentas por Cobrar 0 Préstamos que devengan intereses |  | 25,673,868,775 | ganancia | ER.12 | regla_regex+columna | 0.95 |
| Balance Vecchiola Dic_2016.pdf | Cuentas por cobrar a entidades relacionadas 21,831.772.328 Cuentas por Pagar a Entidades Relacionadas |  | 2,490,673,624 | ganancia | AC.03 | regla_regex | 0.90 |
| Balance Vecchiola Dic_2016.pdf | Activos Intangibles distintos de la plusvalía 940.641.550 Pasivos por Impuestos Diferidos |  | 2,787 | ganancia | ANC.03 | regla_regex | 0.90 |
| Balance Vecchiola Dic_2016.pdf | Capital Emitido |  | 13,955,414,494 | ganancia | PAT.01 | regla_regex | 0.90 |
| EEFF - 2018 Los Nogales.pdf | Cuentas por cobrar a entidades relacionadas, corrientes |  | 0 | ganancia | AC.03 | regla_regex | 0.90 |
| EEFF - 2018 Los Nogales.pdf | Deudores comerciales y otras cuentas por cobrar |  | 324,327 | ganancia | AC.03 | regla_regex | 0.90 |
| EEFF - 2018 Los Nogales.pdf | Inventarios |  | 0 | ganancia | AC.05 | regla_regex | 0.92 |
| EEFF - 2018 Los Nogales.pdf | Activos intangibles |  | 0 | ganancia | ANC.03 | regla_regex | 0.90 |
| EEFF - 2018 Los Nogales.pdf | Capital emitido |  | 1,025,499 | ganancia | PAT.01 | regla_regex | 0.90 |
| EEFF - 2018 Los Nogales.pdf | Ganancia neta |  | 34,504 | ganancia | ER.11 | regla_regex | 0.92 |
| balance general guayacan 2020.pdf | Provisione de Vacaciones | 2116001 | 44,932,361 | pasivo | PC.06 | regla_regex | 0.86 |
| balance general guayacan 2020.pdf | GASTOS DE ADMINISTRACION Y VENT | 3120000 | — | desconocido | ER.04 | regla_regex | 0.88 |
| balance general guayacan 2020.pdf | Remuneraciones Adm. y Venta | 3125001 | 510,711,156 | perdida | ER.01 | regla_regex | 0.90 |
| balance general guayacan 2020.pdf | Remuneraciones Producción | 3125002 | 1,543,865 | perdida | PC.06 | regla_regex | 0.86 |

## Análisis de 31 cuentas con código DIFERENTE entre LEGACY y NEW

### Pareto por mecanismo LEGACY

| # | Mecanismo LEGACY | Cuentas | % | % Acumulado |
|---|------------------|---------|---|-------------|
| 1 | codigo | 9 | 29.0% | 29.0% |
| 2 | desambiguacion_columna_pre | 6 | 19.4% | 48.4% |
| 3 | diccionario_exacto | 6 | 19.4% | 67.7% |
| 4 | correccion_columna_post | 6 | 19.4% | 87.1% |
| 5 | regex | 2 | 6.5% | 93.5% |
| 6 | diccionario_fuzzy | 2 | 6.5% | 100.0% |

### Listado detallado

| PDF | Nombre | Raw | Columna | LEGACY | Método LEGACY | NEW | Método NEW |
|-----|--------|-----|---------|--------|--------------|-----|-----------|
| BALANCE ORIGINAL 2014.pdf | HONORARIOS |  | activo | ER.01 | columna_ambiguo | ER.04 | learning_exact |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | ¡ Ventas |  | ganancia | ER.01 | diccionario_exacto | PAT.01 | learning_exact |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | Honorarios |  | ganancia | ER.01 | columna_ambiguo | ER.04 | learning_exact |
| Balance 2015 - Transp Libardon Ltda.pdf | : VEHICULOS |  | ganancia | ANC.01 | regla_regex | ANC.03 | learning_exact |
| Balance 2016 Abad Garcia y Pons.pdf | ANTICIPO PROVEEDORES |  | ganancia | AC.07 | diccionario_fuzzy | AC.01 | learning_fuzzy |
| Balance 2016 Abad Garcia y Pons.pdf | Ventas |  | ganancia | ER.01 | diccionario_exacto | PAT.01 | learning_exact |
| Balance 2016 Abad Garcia y Pons.pdf | Honorarios |  | ganancia | ER.01 | columna_ambiguo | ER.04 | learning_exact |
| Balance 2016 Abad Garcia y Pons.pdf | Diferencia de Cambio |  | ganancia | ER.15 | diccionario_exacto+columna | ER.09 | learning_exact |
| Balance 2016 Asturias Ltda .pdf | Ventas |  | ganancia | ER.01 | diccionario_exacto | PAT.01 | learning_exact |
| Balance 2016 Campomanes S A .pdf | Intereses |  | ganancia | ER.12 | columna_ambiguo | ER.09 | learning_exact |
| Balance 2016 Campomanes S A .pdf | Honorarios |  | ganancia | ER.01 | columna_ambiguo | ER.04 | learning_exact |
| Balance 2017 - Igesur.pdf | Intereses |  | ganancia | ER.12 | columna_ambiguo | ER.09 | learning_exact |
| Balance 2017 - Igesur.pdf | Diferencia de Cambio |  | ganancia | ER.15 | diccionario_exacto+columna | ER.09 | learning_exact |
| Balance Agricola El Comino dic 2018.pdf | Diferencias de cambio |  | ganancia | ER.15 | diccionario_exacto | ER.09 | learning_fuzzy |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VEHICULOS |  | activo | ANC.01 | regla_regex | ANC.03 | learning_exact |
| Balance Agricola El Dain Ltda 2011 2012.pdf | VENTAS |  | ganancia | ER.01 | diccionario_exacto | PAT.01 | learning_exact |
| Balance Agricola Santa Amelia dic 2018.pdf | Diferencias de cambio |  | perdida | ER.15 | diccionario_exacto | ER.09 | learning_fuzzy |
| Balance General SA JAHUEL 2020 V3.pdf | IVA Credito Fiscal | 1114011 | activo | AC.01 | codigo | AC.07 | learning_exact |
| Balance General SA JAHUEL 2020 V3.pdf | Vehiculos | 1128006 | activo | AC.01 | codigo | ANC.03 | learning_exact |
| Balance General SA JAHUEL 2020 V3.pdf | Herramientas | 1128010 | activo | AC.01 | codigo | ANC.01 | learning_exact |
| Balance General SA JAHUEL 2020 V3.pdf | OTRAS RESERVAS | 2136000 | desconocido | PC.01 | codigo | PAT.02 | learning_exact |
| Balance General SA JAHUEL 2020 V3.pdf | Otras Reservas | 2136099 | pasivo | PC.01 | codigo | PAT.02 | learning_exact |
| Balance General SA JAHUEL 2020 V3.pdf | Otras Ganancias | 4111099 | ganancia | ER.13 | codigo+columna | ER.01 | code |
| Balance Vecchiola Dic_2016.pdf | Diferencias de Cambios |  | ganancia | ER.15 | diccionario_fuzzy | ER.09 | learning_fuzzy |
| balance general guayacan 2020.pdf | Anticipos al Personal | 1113002 | activo | AC.01 | codigo | AC.05 | learning_exact |
| balance general guayacan 2020.pdf | Anticipo de Honorarios | 1113003 | activo | ER.01 | codigo+columna | AC.05 | learning_fuzzy |
| balance general guayacan 2020.pdf | Muebles y Útiles | 1128009 | activo | AC.01 | codigo | ANC.01 | learning_exact |
| balance general guayacan 2020.pdf | Honorarios por Pagar | 2112008 | activo | ER.01 | diccionario_exacto+columna | PC.06 | learning_exact |
| balance general guayacan 2020.pdf | OTRAS RESERVAS | 2136000 | desconocido | PC.01 | codigo | PAT.02 | learning_exact |
| balance general guayacan 2020.pdf | Otras Reservas | 2136099 | pasivo | PC.01 | codigo | PAT.02 | learning_exact |
| balance general guayacan 2020.pdf | Otras Ganancias | 4111099 | ganancia | ER.13 | codigo+columna | ER.01 | code |
