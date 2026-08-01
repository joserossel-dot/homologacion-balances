# Sprint 17 — Análisis de Formatos INBOX

**Generado:** 2026-07-28T00:54:36.969037+00:00
**Fuente:** `datasets/INBOX/` (256 archivos nuevos registrados)
**Pipeline:** ParserPDF (parser_universal) + LayoutDetector
**Archivos procesados exitosamente:** 139 de 256

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Archivos registrados en INBOX | 256 |
| Procesados con parser | 139 |
| Con cuentas detectadas | 134 |
| Sin cuentas (vacíos/corruptos) | 5 |
| Con errores | 0 |
| No procesados (timeout/pendientes) | 117 |
| Total cuentas extraídas | 19383 |

### Categorías Recomendadas

| Categoría | Cantidad |
|-----------|---------|
| **TRAINING** | **39** |
| **HOLDOUT** | **88** |
| **STRESS** | **122** |
| **REJECTED** | **7** |

### Distribución de Familias de Formato

| Familia | Cantidad | % |
|---------|----------|---|
| balance_estandar | 100 | 39.1% |
| pre_balance | 33 | 12.9% |
| eeff_completo | 32 | 12.5% |
| tributario | 24 | 9.4% |
| eeff_auditados | 20 | 7.8% |
| balance_simple | 16 | 6.2% |
| informe_tasacion | 8 | 3.1% |
| resultados | 6 | 2.3% |
| desconocido | 5 | 2.0% |
| cpt_tasacion | 5 | 2.0% |
| consolidado | 3 | 1.2% |
| anexo_activo_fijo | 2 | 0.8% |
| notas_explicativas | 2 | 0.8% |

### Estado vs Formatos Conocidos

| Estado | Cantidad | % |
|--------|----------|---|
| KNOWN_SUPPORTED | 135 | 52.7% |
| PARTIALLY_SUPPORTED | 61 | 23.8% |
| UNKNOWN_OR_INVALID | 43 | 16.8% |
| NEW_FORMAT | 17 | 6.6% |

## Detalle por Archivo

| # | Archivo | Empresa | Año | Págs | Familia | Código | OCR | Cuentas | Headers | Tiempo | Estado | Categoría |
|---|---------|---------|-----|------|---------|--------|-----|---------|---------|--------|--------|-----------|
| 1 | 1.- BCE TRIBUTARIO 2021 INGEFI | 1. BCE INGEFIR | 2021 | 3 | tributario | punto | S | 103 | activo,pasiv | 21.953 | KNOWN_SUPPORTED | HOLDOUT |
| 2 | 10.2023 BALANCE INVERSIONES PD | 10.2023 INVERS | 2023 | 2 | balance_estanda | guion | N | 94 | resultado,co | 1.195 | KNOWN_SUPPORTED | HOLDOUT |
| 3 | 10.2023 BALANCE POWER PRO.pdf | 10.2023 POWER  | 2023 | 2 | balance_estanda | guion | N | 82 | resultado,co | 1.0 | KNOWN_SUPPORTED | HOLDOUT |
| 4 | 10.2023 BALANCE RUTA RENTAL.pd | 10.2023 RUTA R | 2023 | 2 | balance_estanda | guion | N | 73 | resultado,co | 0.907 | KNOWN_SUPPORTED | HOLDOUT |
| 5 | 2022 Balance Firmado Geslog.pd | Firmado Geslog | 2022 | 2 | balance_estanda | punto | N | 126 | activo,pasiv | 0.716 | KNOWN_SUPPORTED | HOLDOUT |
| 6 | 2024- Pre_balance_Chilolac_202 | Pre Chilolac f | 2024 | 8 | pre_balance | sin_codi | S | 232 | activo,resul | 44.714 | KNOWN_SUPPORTED | TRAINING |
| 7 | 3.- BCE TRIBUTARIO 2023 INGEFI | 3. BCE INGEFIR | 2023 | 4 | tributario | punto | S | 147 | activo,pasiv | 26.694 | KNOWN_SUPPORTED | HOLDOUT |
| 8 | 7.- BCE TRIBUTARIO 2024 INGEFI | 7. BCE INGEFIR | 2024 | 3 | tributario | punto | S | 126 | activo,pasiv | 37.054 | KNOWN_SUPPORTED | HOLDOUT |
| 9 | 8_balance_tributario_CREDISR_2 | 8 CREDISR | 2022 | 1 | tributario | compacto | N | 49 | resultado,sa | 0.545 | KNOWN_SUPPORTED | STRESS |
| 10 | Anexo 1 ACT FIJO MEGAMERCADOS  | Anexo 1 ACT FI | 2019 | 2 | anexo_activo_fi | sin_codi | N | 94 | activo | 1.354 | NEW_FORMAT | HOLDOUT |
| 11 | Anexo 1 ACT FIJO SOC SUPERMERC | Anexo 1 ACT FI | 2019 | 1 | anexo_activo_fi | sin_codi | N | 19 | activo,activ | 0.312 | NEW_FORMAT | STRESS |
| 12 | BALANCE 2016 AG E INM EL DAIN. | AG E INM EL | 2016 | 3 | eeff_completo | sin_codi | S | 161 | resultado,sa | 19.18 | PARTIALLY_SUPPORTE | HOLDOUT |
| 13 | BALANCE 2016 AG E INM SAN FELI | AG E INM SAN | 2016 | 4 | eeff_completo | sin_codi | S | 229 | resultado,sa | 24.391 | PARTIALLY_SUPPORTE | TRAINING |
| 14 | BALANCE 2016_43bfd7.pdf | 43bfd7 | 2016 | 4 | eeff_completo | sin_codi | N | 219 | activo,pasiv | 2.611 | PARTIALLY_SUPPORTE | TRAINING |
| 15 | BALANCE 2017 G FUTURO.PDF | G FUTURO | 2017 | ? | desconocido | sin_codi | S | 0 | ? | 0.004 | UNKNOWN_OR_INVALID | REJECTED |
| 16 | BALANCE 2017 LI Y CHAN.PDF | LI Y CHAN | 2017 | ? | desconocido | sin_codi | S | 0 | ? | 0.005 | UNKNOWN_OR_INVALID | REJECTED |
| 17 | BALANCE 2020 Regional SpA 26.0 | Regional SpA 2 | 2020 | 4 | eeff_completo | sin_codi | S | 196 | resultado,sa | 34.224 | PARTIALLY_SUPPORTE | HOLDOUT |
| 18 | BALANCE 2021 Regional SpA 26.0 | Regional SpA 2 | 2021 | ? | desconocido | sin_codi | S | 0 | ? | 0.006 | UNKNOWN_OR_INVALID | REJECTED |
| 19 | BALANCE 2021 SANTA TERESA FIRM | SANTA TERESA F | 2021 | 17 | eeff_completo | sin_codi | S | 455 | resultado,ac | 75.431 | PARTIALLY_SUPPORTE | TRAINING |
| 20 | BALANCE CORREGIDO SAN FELIX 20 | CORREGIDO SAN  | 2015 | 1 | balance_estanda | sin_codi | S | 52 | resultado,co | 47.853 | KNOWN_SUPPORTED | STRESS |
| 21 | BALANCE CORREGIDO SAN FELIX 20 | CORREGIDO SAN  | 2015 | 1 | balance_simple | sin_codi | S | 37 | resultado,co | 43.371 | KNOWN_SUPPORTED | STRESS |
| 22 | BALANCE DAIN 2015 hoja 1.pdf | DAIN hoja 1 | 2015 | 1 | balance_estanda | sin_codi | S | 52 | resultado,co | 45.456 | KNOWN_SUPPORTED | STRESS |
| 23 | BALANCE DAIN 2015 hoja 2 (2).p | DAIN hoja 2 | 2015 | 1 | balance_simple | sin_codi | S | 31 | ? | 37.444 | KNOWN_SUPPORTED | STRESS |
| 24 | BALANCE DALMACIA 1 2016.pdf | DALMACIA 1 | 2016 | 1 | balance_simple | sin_codi | N | 35 | resultado,ac | 0.399 | KNOWN_SUPPORTED | STRESS |
| 25 | BALANCE DALMACIA 2 2016.pdf | DALMACIA 2 | 2016 | 1 | balance_simple | sin_codi | N | 38 | resultado,ac | 0.402 | KNOWN_SUPPORTED | STRESS |
| 26 | BALANCE EL DAIN 2014-2015.pdf | EL DAIN | 2015 | 4 | eeff_completo | sin_codi | S | 178 | perdida | 49.062 | PARTIALLY_SUPPORTE | HOLDOUT |
| 27 | BALANCE GENERAL 2023 REDESA SP | REDESA SPA | 2023 | 3 | balance_estanda | compacto | S | 109 | pasivo,perdi | 22.916 | KNOWN_SUPPORTED | HOLDOUT |
| 28 | BALANCE GENERAL 2023 SOC. DE I | SOC. DE INVERS | 2023 | 2 | balance_estanda | compacto | S | 70 | activo,pasiv | 16.344 | KNOWN_SUPPORTED | HOLDOUT |
| 29 | BALANCE GENERAL 2024 REDESA SP | REDESA SPA | 2024 | 6 | eeff_completo | compacto | S | 260 | activo,resul | 42.878 | PARTIALLY_SUPPORTE | TRAINING |
| 30 | BALANCE GENERAL 2024 SOC. DE I | SOC. DE INVERS | 2024 | 3 | balance_estanda | compacto | S | 121 | activo,resul | 22.441 | KNOWN_SUPPORTED | HOLDOUT |
| 31 | BALANCE LOS LIRIOS + CAPITAL P | LOS LIRIOS + C | ? | 8 | eeff_completo | sin_codi | S | 398 | resultado,sa | 51.692 | PARTIALLY_SUPPORTE | TRAINING |
| 32 | BALANCE PORT 2021.pdf | PORT | 2021 | 2 | balance_estanda | punto | N | 85 | resultado,co | 2.836 | KNOWN_SUPPORTED | HOLDOUT |
| 33 | BALANCE SAN FELIX 2014-2015.pd | SAN FELIX | 2015 | 4 | eeff_completo | sin_codi | S | 166 | activo | 43.772 | PARTIALLY_SUPPORTE | HOLDOUT |
| 34 | BALANCE TRIBUTARIO INMOBILIARI | INMOBILIARIA f | 2023 | 2 | tributario | sin_codi | S | 150 | codigo,pasiv | 32.948 | KNOWN_SUPPORTED | HOLDOUT |
| 35 | Balance  Port  2022 final.pdf | Port | 2022 | 2 | balance_estanda | punto | N | 91 | resultado,re | 2.934 | KNOWN_SUPPORTED | HOLDOUT |
| 36 | Balance  individual Agricola L | individual Agr | 2018 | 3 | balance_estanda | compacto | S | 86 | activo,pasiv | 23.815 | KNOWN_SUPPORTED | HOLDOUT |
| 37 | Balance 12_2015.pdf | Balance 12 201 | 2015 | 1 | balance_simple | sin_codi | N | 27 | patrimonio,a | 0.36 | KNOWN_SUPPORTED | STRESS |
| 38 | Balance 2014 Com San Ignaco Lt | Com San Ignaco | 2014 | 3 | balance_estanda | sin_codi | N | 72 | activo,codig | 2.71 | KNOWN_SUPPORTED | HOLDOUT |
| 39 | Balance 2014 Lacteos SI.pdf | Lacteos SI | 2014 | 4 | balance_estanda | sin_codi | N | 102 | activo,activ | 3.962 | KNOWN_SUPPORTED | HOLDOUT |
| 40 | Balance 2015 - Abad Garcia y P | Abad Garcia y  | 2015 | 5 | eeff_completo | sin_codi | S | 182 | activo,pasiv | 27.938 | PARTIALLY_SUPPORTE | HOLDOUT |
| 41 | Balance 2015 - Comercial Astur | Comercial Astu | 2015 | 4 | eeff_completo | sin_codi | S | 159 | activo,pasiv | 23.388 | PARTIALLY_SUPPORTE | HOLDOUT |
| 42 | Balance 2015 - Soc Com e Inv L | Soc Com e Inv | 2015 | 4 | eeff_completo | sin_codi | S | 153 | activo,pasiv | 22.912 | PARTIALLY_SUPPORTE | HOLDOUT |
| 43 | Balance 2015 - Soc de Inv Camp | Soc de Inv Cam | 2015 | 3 | balance_estanda | sin_codi | S | 111 | activo,pasiv | 18.408 | KNOWN_SUPPORTED | HOLDOUT |
| 44 | Balance 2015 Agroexportaciones | Agroexportacio | 2015 | 4 | balance_estanda | sin_codi | N | 101 | codigo,resul | 4.183 | KNOWN_SUPPORTED | HOLDOUT |
| 45 | Balance 2015 Lacteos San Ignac | Lacteos San Ig | 2015 | 4 | balance_estanda | sin_codi | N | 109 | activo,activ | 4.193 | KNOWN_SUPPORTED | HOLDOUT |
| 46 | Balance 2016 Campoamor S A .pd | Campoamor S A | 2016 | 3 | balance_estanda | sin_codi | S | 104 | activo,pasiv | 17.59 | KNOWN_SUPPORTED | HOLDOUT |
| 47 | Balance 2016 La Santina S A .p | La Santina S A | 2016 | 3 | balance_estanda | sin_codi | S | 103 | activo,pasiv | 17.243 | KNOWN_SUPPORTED | HOLDOUT |
| 48 | Balance 2016 Transportes Libar | Transportes Li | 2016 | 2 | balance_estanda | sin_codi | S | 72 | activo,pasiv | 12.06 | KNOWN_SUPPORTED | HOLDOUT |
| 49 | Balance 2016.pdf | Balance 2016 | 2016 | 3 | eeff_completo | sin_codi | S | 152 | resultado,sa | 19.454 | PARTIALLY_SUPPORTE | HOLDOUT |
| 50 | Balance 2017 - Inversiones Lí | Inversiones Li | 2017 | 1 | balance_simple | sin_codi | N | 27 | activo,pasiv | 0.156 | KNOWN_SUPPORTED | STRESS |
| 51 | Balance 2017 - Mar Vivo.pdf | Mar Vivo | 2017 | 2 | balance_estanda | sin_codi | S | 62 | activo,pasiv | 10.308 | KNOWN_SUPPORTED | HOLDOUT |
| 52 | Balance 2017 Agricola el Jardi | Agricola el Ja | 2017 | 2 | balance_estanda | punto | N | 94 | resultado,sa | 0.672 | KNOWN_SUPPORTED | HOLDOUT |
| 53 | Balance 2017.pdf | Balance 2017 | 2017 | 3 | eeff_completo | sin_codi | S | 165 | resultado,sa | 21.092 | PARTIALLY_SUPPORTE | HOLDOUT |
| 54 | Balance 2018 Agricola el Jardi | Agricola el Ja | 2018 | 2 | balance_estanda | punto | N | 123 | resultado,sa | 0.792 | KNOWN_SUPPORTED | HOLDOUT |
| 55 | Balance 2018 con firma.pdf | con firma | 2018 | 4 | eeff_completo | sin_codi | S | 177 | activo,pasiv | 75.395 | PARTIALLY_SUPPORTE | HOLDOUT |
| 56 | Balance 2019 FIRMADO.pdf | FIRMADO | 2019 | ? | desconocido | sin_codi | S | 0 | ? | 0.004 | UNKNOWN_OR_INVALID | REJECTED |
| 57 | Balance 2020 Istria.pdf | Istria | 2020 | 2 | balance_estanda | sin_codi | N | 69 | resultado,sa | 0.624 | KNOWN_SUPPORTED | HOLDOUT |
| 58 | Balance 2020 Maestranza.pdf | Maestranza | 2020 | 2 | balance_estanda | sin_codi | N | 78 | resultado,sa | 0.698 | KNOWN_SUPPORTED | HOLDOUT |
| 59 | Balance 2021 Istria SA.pdf | Istria SA | 2021 | 2 | balance_estanda | sin_codi | N | 77 | resultado,sa | 0.793 | KNOWN_SUPPORTED | HOLDOUT |
| 60 | Balance 2021 Maestranza.pdf | Maestranza | 2021 | 2 | balance_estanda | sin_codi | N | 82 | resultado,sa | 0.721 | KNOWN_SUPPORTED | HOLDOUT |
| 61 | Balance 2022 Ingenieria.pdf | Ingenieria | 2022 | 1 | balance_simple | sin_codi | N | 41 | resultado,sa | 0.371 | KNOWN_SUPPORTED | STRESS |
| 62 | Balance 2022 Istria SA.pdf | Istria SA | 2022 | 2 | balance_estanda | sin_codi | N | 69 | resultado,sa | 0.676 | KNOWN_SUPPORTED | HOLDOUT |
| 63 | Balance 2022 Maestranza.pdf | Maestranza | 2022 | 2 | balance_estanda | sin_codi | N | 91 | resultado,sa | 0.924 | KNOWN_SUPPORTED | HOLDOUT |
| 64 | Balance 2022 Maquinas.pdf | Maquinas | 2022 | 1 | balance_simple | sin_codi | N | 47 | resultado,sa | 0.434 | KNOWN_SUPPORTED | STRESS |
| 65 | Balance 2022 Transp Istria.pdf | Transp Istria | 2022 | 1 | balance_simple | sin_codi | N | 38 | resultado,sa | 0.367 | KNOWN_SUPPORTED | STRESS |
| 66 | Balance 2023 Central.pdf | Central | 2023 | 6 | eeff_completo | sin_codi | S | 161 | activo,pasiv | 58.186 | PARTIALLY_SUPPORTE | HOLDOUT |
| 67 | Balance 2023 Ingenieria.pdf | Ingenieria | 2023 | 1 | balance_simple | sin_codi | N | 40 | resultado,sa | 0.369 | KNOWN_SUPPORTED | STRESS |
| 68 | Balance 2023 Istria SA.pdf | Istria SA | 2023 | 2 | balance_estanda | sin_codi | N | 61 | resultado,sa | 0.633 | KNOWN_SUPPORTED | HOLDOUT |
| 69 | Balance 2023 Maestranza.pdf | Maestranza | 2023 | 2 | balance_estanda | sin_codi | N | 78 | resultado,sa | 0.68 | KNOWN_SUPPORTED | HOLDOUT |
| 70 | Balance 2023 Maquinas.pdf | Maquinas | 2023 | 2 | balance_estanda | sin_codi | N | 57 | resultado,sa | 0.498 | KNOWN_SUPPORTED | STRESS |
| 71 | Balance 2023 Mega.pdf | Mega | 2023 | 4 | balance_simple | sin_codi | S | 12 | perdida,resu | 20.015 | KNOWN_SUPPORTED | STRESS |
| 72 | Balance 2023 Tributario DSI.pd | DSI | 2023 | 4 | tributario | guion | N | 202 | activo,pasiv | 2.061 | KNOWN_SUPPORTED | TRAINING |
| 73 | Balance 31-12-2018.pdf | 31 12 | 2018 | 7 | eeff_completo | sin_codi | S | 296 | resultado,co | 65.241 | PARTIALLY_SUPPORTE | TRAINING |
| 74 | Balance 31-12-2019.pdf | 31 12 | 2019 | 7 | eeff_completo | guion | S | 318 | resultado,co | 83.06 | PARTIALLY_SUPPORTE | TRAINING |
| 75 | Balance AGRICLA EL RINCON DE N | AGRICLA EL RIN | ? | 2 | balance_estanda | sin_codi | S | 74 | activo,pasiv | 14.681 | KNOWN_SUPPORTED | HOLDOUT |
| 76 | Balance Agricola El Carmelo di | Agricola El Ca | 2018 | 3 | balance_estanda | sin_codi | S | 87 | activo,codig | 20.19 | KNOWN_SUPPORTED | HOLDOUT |
| 77 | Balance Agricola El Dain Ltda  | Agricola El Da | 2013 | 2 | balance_estanda | sin_codi | S | 89 | resultado,co | 13.962 | KNOWN_SUPPORTED | HOLDOUT |
| 78 | Balance Agricola San Felix S A | Agricola San F | 2012 | 4 | eeff_completo | sin_codi | S | 164 | codigo,resul | 30.241 | PARTIALLY_SUPPORTE | HOLDOUT |
| 79 | Balance Agricola San Felix S A | Agricola San F | 2013 | 2 | balance_estanda | sin_codi | S | 89 | resultado,re | 15.012 | KNOWN_SUPPORTED | HOLDOUT |
| 80 | Balance Agricola el Jardin Añ | Agricola el Ja | 2019 | 3 | eeff_completo | punto | N | 153 | resultado,sa | 0.865 | PARTIALLY_SUPPORTE | HOLDOUT |
| 81 | Balance Agrícola Gonzagri Ltd | Agrícola Gonz | ? | 6 | eeff_completo | sin_codi | N | 632 | ? | 2.972 | PARTIALLY_SUPPORTE | TRAINING |
| 82 | Balance Agrícola González Lt | Agrícola Gonz | ? | 7 | eeff_completo | sin_codi | N | 600 | ? | 3.492 | PARTIALLY_SUPPORTE | TRAINING |
| 83 | Balance Agroex 2014.pdf | Agroex | 2014 | 3 | balance_estanda | sin_codi | N | 86 | codigo,resul | 3.352 | KNOWN_SUPPORTED | HOLDOUT |
| 84 | Balance Alto 31-12-2016 (2) (1 | Alto 31 12 | 2016 | 5 | eeff_completo | compacto | S | 203 | activo,pasiv | 41.581 | PARTIALLY_SUPPORTE | TRAINING |
| 85 | Balance Architec 2020 (Firmado | Architec | 2020 | 2 | balance_estanda | punto | S | 82 | resultado,re | 17.663 | KNOWN_SUPPORTED | HOLDOUT |
| 86 | Balance Architec 2021 (Firmado | Architec | 2021 | 2 | balance_estanda | sin_codi | S | 76 | resultado,re | 16.37 | KNOWN_SUPPORTED | HOLDOUT |
| 87 | Balance Architec 2022 (Firmado | Architec | 2022 | 2 | balance_estanda | punto | S | 75 | resultado,re | 16.247 | KNOWN_SUPPORTED | HOLDOUT |
| 88 | Balance Asipac 2015.pdf | Asipac | 2015 | 6 | balance_simple | sin_codi | S | 14 | ? | 27.671 | KNOWN_SUPPORTED | STRESS |
| 89 | Balance Clinica Hyperbaric 202 | Clinica Hyperb | 2025 | 1 | balance_simple | sin_codi | N | 29 | resultado,sa | 0.343 | KNOWN_SUPPORTED | STRESS |
| 90 | Balance El Dain 2016.pdf | El Dain | 2016 | 3 | eeff_completo | sin_codi | N | 160 | activo,pasiv | 0.521 | PARTIALLY_SUPPORTE | HOLDOUT |
| 91 | Balance Esperanza 2020 (Firmad | Esperanza | 2020 | 2 | balance_estanda | punto | S | 87 | resultado,re | 16.392 | KNOWN_SUPPORTED | HOLDOUT |
| 92 | Balance Esperanza 2020 (Firmad | Esperanza e845 | 2020 | 2 | balance_estanda | punto | S | 138 | resultado,re | 20.27 | KNOWN_SUPPORTED | HOLDOUT |
| 93 | Balance Esperanza 2021 (Firmad | Esperanza | 2021 | 3 | balance_estanda | punto | S | 110 | resultado,re | 21.281 | KNOWN_SUPPORTED | HOLDOUT |
| 94 | Balance Esperanza 2022 (Firmad | Esperanza | 2022 | 3 | balance_estanda | punto | S | 107 | resultado,re | 20.632 | KNOWN_SUPPORTED | HOLDOUT |
| 95 | Balance Exportadora Gonzagri.p | Exportadora Go | ? | 6 | eeff_completo | sin_codi | N | 631 | ? | 2.6 | PARTIALLY_SUPPORTE | TRAINING |
| 96 | Balance Frio 2020 (Firmado).pd | Frio | 2020 | 2 | balance_estanda | sin_codi | S | 73 | resultado,re | 15.416 | KNOWN_SUPPORTED | HOLDOUT |
| 97 | Balance Frio 2021 (Firmado).pd | Frio | 2021 | 2 | balance_estanda | sin_codi | S | 78 | resultado,re | 16.028 | KNOWN_SUPPORTED | HOLDOUT |
| 98 | Balance Frio 2022 (Firmado).pd | Frio | 2022 | 2 | balance_estanda | sin_codi | S | 72 | resultado,re | 15.482 | KNOWN_SUPPORTED | HOLDOUT |
| 99 | Balance Frutera 2020 (Firmado) | Frutera | 2020 | 4 | balance_estanda | punto | S | 140 | resultado,re | 27.204 | KNOWN_SUPPORTED | HOLDOUT |
| 100 | Balance Frutera 2021 (Firmado) | Frutera | 2021 | 4 | balance_estanda | sin_codi | S | 146 | resultado,re | 26.066 | KNOWN_SUPPORTED | HOLDOUT |
| 101 | Balance Frutera 2022 (Firmado) | Frutera | 2022 | 4 | balance_estanda | sin_codi | S | 150 | resultado,re | 25.925 | KNOWN_SUPPORTED | HOLDOUT |
| 102 | Balance General 2023.pdf | Balance Genera | 2023 | 4 | balance_estanda | compacto | S | 61 | activo,activ | 32.781 | KNOWN_SUPPORTED | HOLDOUT |
| 103 | Balance General Año 2016 firm | Año firmado | 2016 | ? | desconocido | sin_codi | S | 0 | ? | 0.005 | UNKNOWN_OR_INVALID | REJECTED |
| 104 | Balance General al 31 de dicie | al 31 de Regio | 2023 | 4 | eeff_completo | sin_codi | S | 191 | activo,resul | 30.933 | PARTIALLY_SUPPORTE | HOLDOUT |
| 105 | Balance General final año 202 | año Regional  | 2022 | 4 | eeff_completo | sin_codi | S | 187 | resultado,sa | 25.771 | PARTIALLY_SUPPORTE | HOLDOUT |
| 106 | Balance Gonzagri S.A.pdf | Gonzagri S.A | ? | 2 | eeff_completo | sin_codi | N | 212 | ? | 0.983 | PARTIALLY_SUPPORTE | TRAINING |
| 107 | Balance Inmob 2015.pdf | Inmob | 2015 | 3 | balance_simple | sin_codi | S | 11 | resultado,co | 15.555 | KNOWN_SUPPORTED | STRESS |
| 108 | Balance Los Robles 2020 (Firma | Los Robles | 2020 | 2 | balance_estanda | sin_codi | S | 65 | resultado,ac | 14.701 | KNOWN_SUPPORTED | HOLDOUT |
| 109 | Balance Los Robles 2021 (Firma | Los Robles | 2021 | 2 | balance_estanda | sin_codi | S | 71 | resultado,re | 15.398 | KNOWN_SUPPORTED | HOLDOUT |
| 110 | Balance Los Robles 2022 (Firma | Los Robles | 2022 | 2 | balance_estanda | sin_codi | S | 69 | resultado,re | 15.871 | KNOWN_SUPPORTED | HOLDOUT |
| 111 | Balance Mega 2015.pdf | Mega | 2015 | 6 | balance_simple | sin_codi | S | 16 | resultado,co | 31.219 | KNOWN_SUPPORTED | STRESS |
| 112 | Balance Sup Central 2015.pdf | Sup Central | 2015 | 5 | balance_simple | sin_codi | S | 15 | resultado,co | 23.42 | KNOWN_SUPPORTED | STRESS |
| 113 | Balance TE 12-2023.pdf | TE 12 | 2023 | 3 | balance_estanda | sin_codi | S | 135 | activo,pasiv | 26.237 | KNOWN_SUPPORTED | HOLDOUT |
| 114 | Balance Tributario 2022 Claps  | Claps Firmado | 2022 | 2 | tributario | compacto | N | 55 | activo,pasiv | 0.496 | KNOWN_SUPPORTED | STRESS |
| 115 | Balance Tributario 2022 Wilug  | Wilug Minería | 2022 | 2 | tributario | compacto | N | 100 | activo,pasiv | 1.992 | KNOWN_SUPPORTED | HOLDOUT |
| 116 | Balance Tributario 2023 (2).pd | Balance Tribut | 2023 | 7 | tributario | sin_codi | S | 310 | resultado,co | 57.27 | KNOWN_SUPPORTED | TRAINING |
| 117 | Balance Tributario Chemo S.A D | Chemo S.A Dic. | 2020 | 1 | tributario | sin_codi | S | 23 | resultado,co | 32.481 | KNOWN_SUPPORTED | STRESS |
| 118 | Balance Tributario DSI 2024.pd | DSI | 2024 | 5 | tributario | punto | N | 209 | activo,pasiv | 2.957 | KNOWN_SUPPORTED | TRAINING |
| 119 | Balance Tributario a diciembre | a 31 de Firmad | 2015 | 2 | tributario | sin_codi | S | 78 | resultado,sa | 13.607 | KNOWN_SUPPORTED | HOLDOUT |
| 120 | Balance Tributario a diciembre | a 31 de de | 2016 | 2 | tributario | sin_codi | S | 89 | resultado,sa | 16.809 | KNOWN_SUPPORTED | HOLDOUT |
| 121 | Balance Tributario a diciembre | a 31 de 2016, | 2016 | 2 | tributario | sin_codi | S | 64 | resultado,sa | 14.337 | KNOWN_SUPPORTED | HOLDOUT |
| 122 | Balance Tributario a diciembre | a 31 de 2016, | 2016 | 2 | tributario | sin_codi | S | 62 | resultado,sa | 13.711 | KNOWN_SUPPORTED | HOLDOUT |
| 123 | Balance Tributario a diciembre | a 31 de 2017, | 2017 | 1 | tributario | sin_codi | S | 30 | resultado,sa | 8.107 | KNOWN_SUPPORTED | STRESS |
| 124 | Balance Tributario a diciembre | a 31 de 2017, | 2017 | 1 | tributario | sin_codi | S | 36 | resultado,sa | 8.484 | KNOWN_SUPPORTED | STRESS |
| 125 | Balance Tributario a diciembre | a 31 de 2017, | 2017 | 2 | tributario | sin_codi | S | 99 | resultado,sa | 16.358 | KNOWN_SUPPORTED | HOLDOUT |
| 126 | Balance Tributario a diciembre | a 31 de 2017, | 2017 | 2 | tributario | sin_codi | S | 57 | resultado,sa | 11.814 | KNOWN_SUPPORTED | STRESS |
| 127 | Balance Tributario a diciembre | a 31 de 2017, | 2017 | 3 | tributario | sin_codi | S | 119 | resultado,sa | 19.583 | KNOWN_SUPPORTED | HOLDOUT |
| 128 | Balance Viña Folatre.pdf | Viña Folatre | ? | 8 | eeff_completo | sin_codi | N | 609 | ? | 3.036 | PARTIALLY_SUPPORTE | TRAINING |
| 129 | Balance agricola 2023.pdf | agricola | 2023 | 3 | balance_estanda | sin_codi | N | 128 | resultado,sa | 1.44 | KNOWN_SUPPORTED | HOLDOUT |
| 130 | Balance al 31-12-2019 Puerta d | al 31 12 Puert | 2019 | 1 | balance_estanda | guion | N | 51 | resultado,co | 0.435 | KNOWN_SUPPORTED | STRESS |
| 131 | Balance división al 31 de Ago | división al 3 | ? | 1 | balance_estanda | sin_codi | S | 66 | activo,activ | 72.1 | KNOWN_SUPPORTED | HOLDOUT |
| 132 | Balance inmobiliaria 2023.pdf | inmobiliaria | 2023 | 4 | balance_estanda | compacto | N | 128 | resultado,sa | 1.583 | KNOWN_SUPPORTED | HOLDOUT |
| 133 | Balance ryc 2023.pdf | ryc | 2023 | 4 | eeff_completo | sin_codi | N | 191 | resultado,sa | 2.291 | PARTIALLY_SUPPORTE | HOLDOUT |
| 134 | Balance y EEFF -2023.pdf | Balance y EEFF | 2023 | 8 | eeff_completo | sin_codi | S | 550 | activo,pasiv | 138.124 | PARTIALLY_SUPPORTE | TRAINING |
| 135 | Balance y EERR Exportadora Agu | y EERR Exporta | 2017 | 3 | resultados | sin_codi | S | 76 | activo,codig | 21.003 | PARTIALLY_SUPPORTE | HOLDOUT |
| 136 | BalanceDic2018.pdf | BalanceDic2018 | 2018 | 3 | balance_estanda | sin_codi | N | 99 | resultado,sa | 0.622 | KNOWN_SUPPORTED | HOLDOUT |
| 137 | Balances 2015-2014 Inmobiliari | Balances Inmob | 2014 | 4 | balance_estanda | sin_codi | S | 113 | activo,activ | 17.087 | KNOWN_SUPPORTED | HOLDOUT |
| 138 | Balances 2015-2014 Inversiones | Balances Inver | 2014 | 4 | balance_estanda | sin_codi | S | 119 | activo,activ | 20.091 | KNOWN_SUPPORTED | HOLDOUT |
| 139 | Balances Grupo.pdf | Balances Grupo | ? | 48 | eeff_completo | sin_codi | N | 2268 | activo,resul | 12.529 | PARTIALLY_SUPPORTE | TRAINING |
| 140 | Balances respaldo ventas.pdf | Balances respa | ? | 13 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 141 | Bce.2016 Agric. Santa Malva.pd | Bce.2016 Agric | 2016 | 4 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 142 | Bce.2016 Barraca Castro.pdf | Bce.2016 Barra | 2016 | 8 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 143 | Bce.2016 Inmobiliaria Sta. Mal | Bce.2016 Inmob | 2016 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 144 | Bce.2016 TSM.PDF | Bce.2016 TSM | 2016 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 145 | Bce.2016 Transp. El Diamante.p | Bce.2016 Trans | 2016 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 146 | CPTAgrGonzagriLtda.pdf | CPTAgrGonzagri | ? | 41 | cpt_tasacion | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 147 | CPTAgrGonzalezLtda.pdf | CPTAgrGonzalez | ? | 41 | cpt_tasacion | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 148 | CPTExportadora.pdf | CPTExportadora | ? | 41 | cpt_tasacion | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 149 | CPTGonzagriS.A..pdf | CPTGonzagriS.A | ? | 41 | cpt_tasacion | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 150 | CPTVin¦âaFolatre.pdf | CPTVin¦âaFola | ? | 41 | cpt_tasacion | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 151 | Cómo consolidar un balance.pd | Cómo consolid | ? | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 152 | David del Curto EEFF 2018 Cons | David del Curt | 2018 | 113 | consolidado | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 153 | EEFF 16 - RENTAS 17 - GRUPO CA | 16 RENTAS 17 G | ? | 28 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 154 | EEFF 2016-2015 Sociedad Médic | Sociedad Médi | 2015 | 54 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 155 | EEFF 2018  Terra.pdf | Terra | 2018 | 8 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 156 | EEFF 2018 Agroindustrial SURFR | Agroindustrial | 2018 | 48 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 157 | EEFF 2018 Purefruit S A.pdf | Purefruit S A | 2018 | 38 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 158 | EEFF 31.12.2019 MEDITERRANEO A | 31.12.2019 MED | 2019 | 37 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 159 | EEFF Baika S.A. 31-12-2018 con | Baika S.A. 31  | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 160 | EEFF Baika S.A. 31-12-2018 ind | Baika S.A. 31  | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 161 | EEFF IFRS Vitapro 2017.pdf | IFRS Vitapro | 2017 | 54 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 162 | EEFF Inmobiliaria LA Ltda. al  | Inmobiliaria L | 2017 | 23 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 163 | EEFF PNV S.A. 31-12-2018.pdf | PNV S.A. 31 12 | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 164 | EEFF SJF S.A. 31-12-2018 indiv | SJF S.A. 31 12 | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 165 | EEFF SJF y filiales consolidad | SJF y filiales | 2019 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 166 | EEFF T y G Vecchiola 2016-2015 | T y G Vecchiol | 2015 | 53 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 167 | EEFF Temporada 2018-2017 A  El | Temporada A El | 2017 | 3 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 168 | EEFF Temporada 2018-2017 A  Sa | Temporada A Sa | 2017 | 3 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 169 | EEFF VDS S.A. 31-12-2018 conso | VDS S.A. 31 12 | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 170 | EEFF VDS S.A. 31-12-2018 indiv | VDS S.A. 31 12 | 2018 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 171 | EEFF preliminar TyG DIC_2016.p | preliminar TyG | 2016 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 172 | EEFF_TRAF_2016.pdf | TRAF | 2016 | 2 | eeff_auditados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | TRAINING |
| 173 | EERR AICSA 2019.pdf | EERR AICSA | 2019 | 1 | resultados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 174 | EERR CENTRAL 2019.pdf | EERR CENTRAL | 2019 | 1 | resultados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 175 | EERR INMOBILIARIA 2019.pdf | EERR INMOBILIA | 2019 | 1 | resultados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 176 | EERR MEGAMERCADOS 2019.pdf | EERR MEGAMERCA | 2019 | 1 | resultados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 177 | EERR SUPER CUGAT 2019.pdf | EERR SUPER CUG | 2019 | 1 | resultados | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 178 | Estado de Situacion Edgardo Me | de Edgardo Mey | ? | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 179 | F22 Inmobiliaria 76790840-7 20 | F22 Inmobiliar | 2020 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 180 | IT_0331_EL TRAPICHE_SABGRADA F | IT 0331 EL TRA | ? | 26 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 181 | IT_0335_Gonzagri Ltda_79606270 | IT 0335 Gonzag | ? | 8 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 182 | IT_0336_Lisonjera Lote 4_Packi | IT 0336 Lisonj | ? | 21 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 183 | IT_0338_Gonzagri Ltda_79606270 | IT 0338 Gonzag | ? | 8 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 184 | IT_0340_Gonzagri Ltda_79606270 | IT 0340 Gonzag | ? | 8 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 185 | IT_0341_Gonzagri Ltda_79606270 | IT 0341 Gonzag | ? | 10 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 186 | IT_0342_Gonzagri Ltda_79606270 | IT 0342 Gonzag | ? | 8 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 187 | IT_0343_Teniente Cruz_Folatre_ | IT 0343 Tenien | ? | 17 | informe_tasacio | ? | ? | -1 | ? | ? | NEW_FORMAT | STRESS |
| 188 | Inm.OVALLE 2015.pdf | Inm.OVALLE | 2015 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 189 | Inm.OVALLE 2016.pdf | Inm.OVALLE | 2016 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 190 | Inm.OVALLE 2017.pdf | Inm.OVALLE | 2017 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 191 | Inv.JIM 2015.pdf | Inv.JIM | 2015 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 192 | Inv.JIM 2016.pdf | Inv.JIM | 2016 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 193 | Inv.JIM 2017.pdf | Inv.JIM | 2017 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 194 | Inv.S.ANITA 2015.pdf | Inv.S.ANITA | 2015 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 195 | Inv.S.ANITA 2016.pdf | Inv.S.ANITA | 2016 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 196 | Inv.S.ANITA 2017.pdf | Inv.S.ANITA | 2017 | 1 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 197 | Inversiones Brit SA - Balance  | Inversiones Br | 2023 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 198 | MFCB - Balance 2015 Nivel 3, f | MFCB Nivel 3,  | 2016 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 199 | MFCB - Balance 2016 Nivel 3, f | MFCB Nivel 3,  | 2017 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 200 | MFCB - Pre-Balance 2017 Oct.pd | MFCB Pre Oct | 2017 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 201 | Notas Explicativas Central 201 | Notas Explicat | 2019 | 52 | notas_explicati | ? | ? | -1 | ? | ? | NEW_FORMAT | REJECTED |
| 202 | Notas Explicativas Inmobiliari | Notas Explicat | 2019 | 48 | notas_explicati | ? | ? | -1 | ? | ? | NEW_FORMAT | REJECTED |
| 203 | OK BALANCE 2018 CARRIZALILLO.P | OK CARRIZALILL | 2018 | 5 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 204 | OPE BALANCE 2016.pdf | OPE | 2016 | 4 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 205 | PRE BALANCE 2018.pdf | PRE | 2018 | 3 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 206 | PRE BALANCE AGRICOLA SAN SEBAS | PRE AGRICOLA S | ? | 5 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 207 | PRE-BALANCE AICSA 2015.PDF | PRE AICSA | 2015 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 208 | PRE-BALANCE SOCIEDAD SUPER 201 | PRE SOCIEDAD S | 2015 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 209 | PRE-BALANCES AICSA DICIEMBRE 2 | PRE BALANCES A | 2016 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 210 | PRE-BALANCES SUPER CUGAT DICIE | PRE BALANCES S | 2016 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 211 | Pre Balance Automotriz Rosselo | Pre Automotriz | 2024 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 212 | Pre Balance Emilio Kuncar 2017 | Pre Emilio Kun | 2017 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 213 | Pre Balance FC 06-24.pdf | Pre FC 06 24 | ? | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 214 | Pre Balance LasTranqueras2017. | Pre LasTranque | 2017 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 215 | Pre Balance TE 06-2024.pdf | Pre TE 06 | 2024 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 216 | Pre Balance Tributario CASA Di | Pre CASA v31.0 | 2019 | 5 | tributario | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 217 | Pre Balance Tributario VFCH Di | Pre VFCH v31.0 | 2019 | 6 | tributario | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 218 | Pre Balances Grupo Rosselot al | Pre Balances G | 2024 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 219 | Pre balance 2023 Agrocomercial | Pre Agrocomerc | 2023 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 220 | Pre balance 2023 Andalucía.pd | Pre Andalucía | 2023 | 3 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 221 | Pre balance 2023 Gucam.pdf | Pre Gucam | 2023 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 222 | Pre balance 2023 Gutierrez her | Pre Gutierrez  | 2023 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 223 | Pre balance 2023 Libra.pdf | Pre Libra | 2023 | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 224 | Pre balance 2023 Mallorca.pdf | Pre Mallorca | 2023 | 3 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 225 | Pre balance 2023 Mayorista ben | Pre Mayorista  | 2023 | 3 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 226 | Pre balance 2023 Samo.pdf | Pre Samo | 2023 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 227 | Pre balance 2023 Transportes.p | Pre Transporte | 2023 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 228 | Pre balance Collipulli Red Soi | Pre Collipulli | 2019 | 2 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 229 | Pre- Balance Nov 2019 Agricola | Pre Nov Agrico | 2019 | 3 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 230 | Pre-Balance Comercializadora 2 | Pre Comerciali | 2018 | 6 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 231 | Pre-Balance Frio DIC.2023.pdf | Pre Frio DIC.2 | 2023 | ? | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 232 | Pre-Balance Frutera SEP.2023 ( | Pre Frutera SE | 2023 | 4 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 233 | Pre-Balance Oscar Prohens Espi | Pre Oscar Proh | 2017 | 4 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 234 | Pre-Balance Sept-24_f.pdf | Pre Sept 24 f | ? | 1 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 235 | Pre-balance Giddings Berries.p | Pre Giddings B | ? | ? | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 236 | Prebalance_Inv. Torabus Ltda 2 | Prebalance Inv | 2023 | 13 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 237 | SANTA TERESA BALANCE 2022 Firm | SANTA TERESA F | 2022 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 238 | Soc Educacional Peniel SA - Ba | Soc Educaciona | 2023 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 239 | Soc de Inversiones Brit Ltda - | Soc de Inversi | ? | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 240 | _balance_tributario_INMOBIIRIA | INMOBIIRIA CLA | 2022 | 1 | tributario | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 241 | baika 15 y 16.pdf | baika 15 y 16 | ? | 62 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 242 | balance cm 2015.pdf | balance cm 201 | 2015 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 243 | balance cm 2016.pdf | balance cm 201 | 2016 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 244 | balance cm 2017.pdf | balance cm 201 | 2017 | 5 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 245 | balance combinado El Comino di | combinado El C | 2018 | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 246 | balance individual Agricola Ce | individual Agr | 2018 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 247 | balance_2022 Inversiones OC Fi | Inversiones OC | 2022 | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 248 | balance_tributario_INVERSIONES | INVERSIONES S  | 2022 | 1 | tributario | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 249 | consolidado sept.pdf | sept | ? | 6 | consolidado | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 250 | consolidado torca 15 y 16.pdf | torca 15 y 16 | ? | 73 | consolidado | ? | ? | -1 | ? | ? | PARTIALLY_SUPPORTE | STRESS |
| 251 | first balances.pdf | first balances | ? | 4 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 252 | inv torca 15 y 16.pdf | inv torca 15 y | ? | 3 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 253 | pre-balance central 2016.pdf | pre central | 2016 | 4 | pre_balance | ? | ? | -1 | ? | ? | KNOWN_SUPPORTED | STRESS |
| 254 | valles del norte sept.pdf | valles del nor | ? | 6 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 255 | valles del sur sept.pdf | valles del sur | ? | 6 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |
| 256 | vilkun 15 y 16.pdf | vilkun 15 y 16 | ? | 2 | balance_estanda | ? | ? | -1 | ? | ? | UNKNOWN_OR_INVALID | STRESS |

## Formatos ya Soportados (KNOWN_SUPPORTED)

**135 archivos** — familias de formato ya cubiertas por el pipeline actual.

| # | Archivo | Familia | Cuentas | Categoría |
|---|---------|---------|---------|-----------|
| 1 | 1.- BCE TRIBUTARIO 2021 INGEFIRE SpA.pdf | tributario | 103 | HOLDOUT |
| 2 | 10.2023 BALANCE INVERSIONES PD.pdf | balance_estandar | 94 | HOLDOUT |
| 3 | 10.2023 BALANCE POWER PRO.pdf | balance_estandar | 82 | HOLDOUT |
| 4 | 10.2023 BALANCE RUTA RENTAL.pdf | balance_estandar | 73 | HOLDOUT |
| 5 | 2022 Balance Firmado Geslog.pdf | balance_estandar | 126 | HOLDOUT |
| 6 | 2024- Pre_balance_Chilolac_2024 firmado.pdf | pre_balance | 232 | TRAINING |
| 7 | 3.- BCE TRIBUTARIO 2023 INGEFIRE SpA.pdf | tributario | 147 | HOLDOUT |
| 8 | 7.- BCE TRIBUTARIO 2024 INGEFIRE SpA (1).pdf | tributario | 126 | HOLDOUT |
| 9 | 8_balance_tributario_CREDISR_2022.pdf | tributario | 49 | STRESS |
| 10 | BALANCE CORREGIDO SAN FELIX 2015 hoja 1.pdf | balance_estandar | 52 | STRESS |
| 11 | BALANCE CORREGIDO SAN FELIX 2015 hoja 2.pdf | balance_simple | 37 | STRESS |
| 12 | BALANCE DAIN 2015 hoja 1.pdf | balance_estandar | 52 | STRESS |
| 13 | BALANCE DAIN 2015 hoja 2 (2).pdf | balance_simple | 31 | STRESS |
| 14 | BALANCE DALMACIA 1 2016.pdf | balance_simple | 35 | STRESS |
| 15 | BALANCE DALMACIA 2 2016.pdf | balance_simple | 38 | STRESS |
| 16 | BALANCE GENERAL 2023 REDESA SPA.pdf | balance_estandar | 109 | HOLDOUT |
| 17 | BALANCE GENERAL 2023 SOC. DE INVERSIONES UNIDEPRO S.A.. | balance_estandar | 70 | HOLDOUT |
| 18 | BALANCE GENERAL 2024 SOC. DE INVERSIONES UNIDEPRO S.A.. | balance_estandar | 121 | HOLDOUT |
| 19 | BALANCE PORT 2021.pdf | balance_estandar | 85 | HOLDOUT |
| 20 | BALANCE TRIBUTARIO INMOBILIARIA DICIEMBRE 2023 firmado. | tributario | 150 | HOLDOUT |
| 21 | Balance  Port  2022 final.pdf | balance_estandar | 91 | HOLDOUT |
| 22 | Balance  individual Agricola La Viñita 2018.pdf | balance_estandar | 86 | HOLDOUT |
| 23 | Balance 12_2015.pdf | balance_simple | 27 | STRESS |
| 24 | Balance 2014 Com San Ignaco Ltda.pdf | balance_estandar | 72 | HOLDOUT |
| 25 | Balance 2014 Lacteos SI.pdf | balance_estandar | 102 | HOLDOUT |
| 26 | Balance 2015 - Soc de Inv Campomanes SA.pdf | balance_estandar | 111 | HOLDOUT |
| 27 | Balance 2015 Agroexportaciones Chile S A .pdf | balance_estandar | 101 | HOLDOUT |
| 28 | Balance 2015 Lacteos San Ignacio Limitada.pdf | balance_estandar | 109 | HOLDOUT |
| 29 | Balance 2016 Campoamor S A .pdf | balance_estandar | 104 | HOLDOUT |
| 30 | Balance 2016 La Santina S A .pdf | balance_estandar | 103 | HOLDOUT |
| 31 | Balance 2016 Transportes Libardom Ltda .pdf | balance_estandar | 72 | HOLDOUT |
| 32 | Balance 2017 - Inversiones Línea Real.pdf | balance_simple | 27 | STRESS |
| 33 | Balance 2017 - Mar Vivo.pdf | balance_estandar | 62 | HOLDOUT |
| 34 | Balance 2017 Agricola el Jardin.pdf | balance_estandar | 94 | HOLDOUT |
| 35 | Balance 2018 Agricola el Jardin.pdf | balance_estandar | 123 | HOLDOUT |
| 36 | Balance 2020 Istria.pdf | balance_estandar | 69 | HOLDOUT |
| 37 | Balance 2020 Maestranza.pdf | balance_estandar | 78 | HOLDOUT |
| 38 | Balance 2021 Istria SA.pdf | balance_estandar | 77 | HOLDOUT |
| 39 | Balance 2021 Maestranza.pdf | balance_estandar | 82 | HOLDOUT |
| 40 | Balance 2022 Ingenieria.pdf | balance_simple | 41 | STRESS |
| 41 | Balance 2022 Istria SA.pdf | balance_estandar | 69 | HOLDOUT |
| 42 | Balance 2022 Maestranza.pdf | balance_estandar | 91 | HOLDOUT |
| 43 | Balance 2022 Maquinas.pdf | balance_simple | 47 | STRESS |
| 44 | Balance 2022 Transp Istria.pdf | balance_simple | 38 | STRESS |
| 45 | Balance 2023 Ingenieria.pdf | balance_simple | 40 | STRESS |
| 46 | Balance 2023 Istria SA.pdf | balance_estandar | 61 | HOLDOUT |
| 47 | Balance 2023 Maestranza.pdf | balance_estandar | 78 | HOLDOUT |
| 48 | Balance 2023 Maquinas.pdf | balance_estandar | 57 | STRESS |
| 49 | Balance 2023 Mega.pdf | balance_simple | 12 | STRESS |
| 50 | Balance 2023 Tributario DSI.pdf | tributario | 202 | TRAINING |
| 51 | Balance AGRICLA EL RINCON DE ÑILHUE S.A. 7-2-18.pdf | balance_estandar | 74 | HOLDOUT |
| 52 | Balance Agricola El Carmelo dic 2018.pdf | balance_estandar | 87 | HOLDOUT |
| 53 | Balance Agricola El Dain Ltda 2013.pdf | balance_estandar | 89 | HOLDOUT |
| 54 | Balance Agricola San Felix S A  2013.pdf | balance_estandar | 89 | HOLDOUT |
| 55 | Balance Agroex 2014.pdf | balance_estandar | 86 | HOLDOUT |
| 56 | Balance Architec 2020 (Firmado).pdf | balance_estandar | 82 | HOLDOUT |
| 57 | Balance Architec 2021 (Firmado).pdf | balance_estandar | 76 | HOLDOUT |
| 58 | Balance Architec 2022 (Firmado).pdf | balance_estandar | 75 | HOLDOUT |
| 59 | Balance Asipac 2015.pdf | balance_simple | 14 | STRESS |
| 60 | Balance Clinica Hyperbaric 2025.pdf | balance_simple | 29 | STRESS |
| 61 | Balance Esperanza 2020 (Firmado).pdf | balance_estandar | 87 | HOLDOUT |
| 62 | Balance Esperanza 2020 (Firmado)_e8457b.pdf | balance_estandar | 138 | HOLDOUT |
| 63 | Balance Esperanza 2021 (Firmado).pdf | balance_estandar | 110 | HOLDOUT |
| 64 | Balance Esperanza 2022 (Firmado).pdf | balance_estandar | 107 | HOLDOUT |
| 65 | Balance Frio 2020 (Firmado).pdf | balance_estandar | 73 | HOLDOUT |
| 66 | Balance Frio 2021 (Firmado).pdf | balance_estandar | 78 | HOLDOUT |
| 67 | Balance Frio 2022 (Firmado).pdf | balance_estandar | 72 | HOLDOUT |
| 68 | Balance Frutera 2020 (Firmado).pdf | balance_estandar | 140 | HOLDOUT |
| 69 | Balance Frutera 2021 (Firmado).pdf | balance_estandar | 146 | HOLDOUT |
| 70 | Balance Frutera 2022 (Firmado).pdf | balance_estandar | 150 | HOLDOUT |
| 71 | Balance General 2023.pdf | balance_estandar | 61 | HOLDOUT |
| 72 | Balance Inmob 2015.pdf | balance_simple | 11 | STRESS |
| 73 | Balance Los Robles 2020 (Firmado).pdf | balance_estandar | 65 | HOLDOUT |
| 74 | Balance Los Robles 2021 (Firmado).pdf | balance_estandar | 71 | HOLDOUT |
| 75 | Balance Los Robles 2022 (Firmado).pdf | balance_estandar | 69 | HOLDOUT |
| 76 | Balance Mega 2015.pdf | balance_simple | 16 | STRESS |
| 77 | Balance Sup Central 2015.pdf | balance_simple | 15 | STRESS |
| 78 | Balance TE 12-2023.pdf | balance_estandar | 135 | HOLDOUT |
| 79 | Balance Tributario 2022 Claps Firmado.pdf | tributario | 55 | STRESS |
| 80 | Balance Tributario 2022 Wilug Minería SpA.pdf | tributario | 100 | HOLDOUT |
| 81 | Balance Tributario 2023 (2).pdf | tributario | 310 | TRAINING |
| 82 | Balance Tributario Chemo S.A Dic.2020.pdf | tributario | 23 | STRESS |
| 83 | Balance Tributario DSI 2024.pdf | tributario | 209 | TRAINING |
| 84 | Balance Tributario a diciembre 31 de 2015 - Firmados.pd | tributario | 78 | HOLDOUT |
| 85 | Balance Tributario a diciembre 31 de 2016 de CyH, firma | tributario | 89 | HOLDOUT |
| 86 | Balance Tributario a diciembre 31 de 2016, Soc. Inmob.  | tributario | 64 | HOLDOUT |
| 87 | Balance Tributario a diciembre 31 de 2016, Soc. de Inv. | tributario | 62 | HOLDOUT |
| 88 | Balance Tributario a diciembre 31 de 2017, Inm. Indepen | tributario | 30 | STRESS |
| 89 | Balance Tributario a diciembre 31 de 2017, Inv. e Inmob | tributario | 36 | STRESS |
| 90 | Balance Tributario a diciembre 31 de 2017, Maq. Ag. CyH | tributario | 99 | HOLDOUT |
| 91 | Balance Tributario a diciembre 31 de 2017, Min. La Rubi | tributario | 57 | STRESS |
| 92 | Balance Tributario a diciembre 31 de 2017, Serv. y Neg. | tributario | 119 | HOLDOUT |
| 93 | Balance agricola 2023.pdf | balance_estandar | 128 | HOLDOUT |
| 94 | Balance al 31-12-2019 Puerta del Barro.pdf | balance_estandar | 51 | STRESS |
| 95 | Balance división al 31 de Agosto ( Inversiones San Ign | balance_estandar | 66 | HOLDOUT |
| 96 | Balance inmobiliaria 2023.pdf | balance_estandar | 128 | HOLDOUT |
| 97 | BalanceDic2018.pdf | balance_estandar | 99 | HOLDOUT |
| 98 | Balances 2015-2014 Inmobiliaria Vecchiola.pdf | balance_estandar | 113 | HOLDOUT |
| 99 | Balances 2015-2014 Inversiones  Vecchiola.pdf | balance_estandar | 119 | HOLDOUT |
| 100 | MFCB - Pre-Balance 2017 Oct.pdf | pre_balance | -1 | STRESS |
| 101 | PRE BALANCE 2018.pdf | pre_balance | -1 | STRESS |
| 102 | PRE BALANCE AGRICOLA SAN SEBASTIAN.pdf | pre_balance | -1 | STRESS |
| 103 | PRE-BALANCE AICSA 2015.PDF | pre_balance | -1 | STRESS |
| 104 | PRE-BALANCE SOCIEDAD SUPER 2015.PDF | pre_balance | -1 | STRESS |
| 105 | PRE-BALANCES AICSA DICIEMBRE 2016.pdf | pre_balance | -1 | STRESS |
| 106 | PRE-BALANCES SUPER CUGAT DICIEMBRE 2016.pdf | pre_balance | -1 | STRESS |
| 107 | Pre Balance Automotriz Rosselot al 31-12-2024.pdf | pre_balance | -1 | STRESS |
| 108 | Pre Balance Emilio Kuncar 2017.pdf | pre_balance | -1 | STRESS |
| 109 | Pre Balance FC 06-24.pdf | pre_balance | -1 | STRESS |
| 110 | Pre Balance LasTranqueras2017.pdf | pre_balance | -1 | STRESS |
| 111 | Pre Balance TE 06-2024.pdf | pre_balance | -1 | STRESS |
| 112 | Pre Balance Tributario CASA Dic 2019 v31.03.pdf | tributario | -1 | STRESS |
| 113 | Pre Balance Tributario VFCH Dic 2019 v31.03.pdf | tributario | -1 | STRESS |
| 114 | Pre Balances Grupo Rosselot al 31-12-2024.pdf | pre_balance | -1 | STRESS |
| 115 | Pre balance 2023 Agrocomercial.pdf | pre_balance | -1 | STRESS |
| 116 | Pre balance 2023 Andalucía.pdf | pre_balance | -1 | STRESS |
| 117 | Pre balance 2023 Gucam.pdf | pre_balance | -1 | STRESS |
| 118 | Pre balance 2023 Gutierrez hermanos.pdf | pre_balance | -1 | STRESS |
| 119 | Pre balance 2023 Libra.pdf | pre_balance | -1 | STRESS |
| 120 | Pre balance 2023 Mallorca.pdf | pre_balance | -1 | STRESS |
| 121 | Pre balance 2023 Mayorista benavente.pdf | pre_balance | -1 | STRESS |
| 122 | Pre balance 2023 Samo.pdf | pre_balance | -1 | STRESS |
| 123 | Pre balance 2023 Transportes.pdf | pre_balance | -1 | STRESS |
| 124 | Pre balance Collipulli Red Soil S.A. 06-2019.pdf | pre_balance | -1 | STRESS |
| 125 | Pre- Balance Nov 2019 Agricola el Jardin.pdf | pre_balance | -1 | STRESS |
| 126 | Pre-Balance Comercializadora 2018.pdf | pre_balance | -1 | STRESS |
| 127 | Pre-Balance Frio DIC.2023.pdf | pre_balance | -1 | STRESS |
| 128 | Pre-Balance Frutera SEP.2023 (Firmado).pdf | pre_balance | -1 | STRESS |
| 129 | Pre-Balance Oscar Prohens Espinosa 2017.pdf | pre_balance | -1 | STRESS |
| 130 | Pre-Balance Sept-24_f.pdf | pre_balance | -1 | STRESS |
| 131 | Pre-balance Giddings Berries.pdf | pre_balance | -1 | STRESS |
| 132 | Prebalance_Inv. Torabus Ltda 2023 (1).pdf | pre_balance | -1 | STRESS |
| 133 | _balance_tributario_INMOBIIRIA_CLAPS_2022.pdf | tributario | -1 | STRESS |
| 134 | balance_tributario_INVERSIONES_S_Y_S_2022.pdf | tributario | -1 | STRESS |
| 135 | pre-balance central 2016.pdf | pre_balance | -1 | STRESS |

## Formatos Parcialmente Soportados (PARTIALLY_SUPPORTED)

**61 archivos** — características parcialmente cubiertas.

| # | Archivo | Familia | Cuentas | Código | Categoría |
|---|---------|---------|---------|--------|-----------|
| 1 | BALANCE 2016 AG E INM EL DAIN.PDF | eeff_completo | 161 | sin_codigo | HOLDOUT |
| 2 | BALANCE 2016 AG E INM SAN FELIX.PDF | eeff_completo | 229 | sin_codigo | TRAINING |
| 3 | BALANCE 2016_43bfd7.pdf | eeff_completo | 219 | sin_codigo | TRAINING |
| 4 | BALANCE 2020 Regional SpA 26.04.22.pdf | eeff_completo | 196 | sin_codigo | HOLDOUT |
| 5 | BALANCE 2021 SANTA TERESA FIRMADO.pdf | eeff_completo | 455 | sin_codigo | TRAINING |
| 6 | BALANCE EL DAIN 2014-2015.pdf | eeff_completo | 178 | sin_codigo | HOLDOUT |
| 7 | BALANCE GENERAL 2024 REDESA SPA.pdf | eeff_completo | 260 | compacto | TRAINING |
| 8 | BALANCE LOS LIRIOS + CAPITAL PROPIO.PDF | eeff_completo | 398 | sin_codigo | TRAINING |
| 9 | BALANCE SAN FELIX 2014-2015.pdf | eeff_completo | 166 | sin_codigo | HOLDOUT |
| 10 | Balance 2015 - Abad Garcia y Pons Ltda.pdf | eeff_completo | 182 | sin_codigo | HOLDOUT |
| 11 | Balance 2015 - Comercial Asturias Ltda.pdf | eeff_completo | 159 | sin_codigo | HOLDOUT |
| 12 | Balance 2015 - Soc Com e Inv La Santina SA.pdf | eeff_completo | 153 | sin_codigo | HOLDOUT |
| 13 | Balance 2016.pdf | eeff_completo | 152 | sin_codigo | HOLDOUT |
| 14 | Balance 2017.pdf | eeff_completo | 165 | sin_codigo | HOLDOUT |
| 15 | Balance 2018 con firma.pdf | eeff_completo | 177 | sin_codigo | HOLDOUT |
| 16 | Balance 2023 Central.pdf | eeff_completo | 161 | sin_codigo | HOLDOUT |
| 17 | Balance 31-12-2018.pdf | eeff_completo | 296 | sin_codigo | TRAINING |
| 18 | Balance 31-12-2019.pdf | eeff_completo | 318 | guion | TRAINING |
| 19 | Balance Agricola San Felix S A  2011 2012.pdf | eeff_completo | 164 | sin_codigo | HOLDOUT |
| 20 | Balance Agricola el Jardin Año 2019 (3).pdf | eeff_completo | 153 | punto | HOLDOUT |
| 21 | Balance Agrícola Gonzagri Ltda.pdf | eeff_completo | 632 | sin_codigo | TRAINING |
| 22 | Balance Agrícola González Ltda.pdf | eeff_completo | 600 | sin_codigo | TRAINING |
| 23 | Balance Alto 31-12-2016 (2) (1).pdf | eeff_completo | 203 | compacto | TRAINING |
| 24 | Balance El Dain 2016.pdf | eeff_completo | 160 | sin_codigo | HOLDOUT |
| 25 | Balance Exportadora Gonzagri.pdf | eeff_completo | 631 | sin_codigo | TRAINING |
| 26 | Balance General al 31 de diciembre 2023 - Regional Spa. | eeff_completo | 191 | sin_codigo | HOLDOUT |
| 27 | Balance General final año 2022 - Regional Spa.pdf | eeff_completo | 187 | sin_codigo | HOLDOUT |
| 28 | Balance Gonzagri S.A.pdf | eeff_completo | 212 | sin_codigo | TRAINING |
| 29 | Balance Viña Folatre.pdf | eeff_completo | 609 | sin_codigo | TRAINING |
| 30 | Balance ryc 2023.pdf | eeff_completo | 191 | sin_codigo | HOLDOUT |
| 31 | Balance y EEFF -2023.pdf | eeff_completo | 550 | sin_codigo | TRAINING |
| 32 | Balance y EERR Exportadora Agua Santa  (USD) 31-12-2017 | resultados | 76 | sin_codigo | HOLDOUT |
| 33 | Balances Grupo.pdf | eeff_completo | 2268 | sin_codigo | TRAINING |
| 34 | David del Curto EEFF 2018 Consolidado BORRADOR (2).pdf | consolidado | -1 | ? | STRESS |
| 35 | EEFF 16 - RENTAS 17 - GRUPO CASA GARCIA.pdf | eeff_auditados | -1 | ? | TRAINING |
| 36 | EEFF 2016-2015 Sociedad Médica de Establecimientos Cli | eeff_auditados | -1 | ? | TRAINING |
| 37 | EEFF 2018  Terra.pdf | eeff_auditados | -1 | ? | TRAINING |
| 38 | EEFF 2018 Agroindustrial SURFRUT Ltda.pdf | eeff_auditados | -1 | ? | TRAINING |
| 39 | EEFF 2018 Purefruit S A.pdf | eeff_auditados | -1 | ? | TRAINING |
| 40 | EEFF 31.12.2019 MEDITERRANEO AUTOMOTORES.pdf | eeff_auditados | -1 | ? | TRAINING |
| 41 | EEFF Baika S.A. 31-12-2018 consolidado.pdf | eeff_auditados | -1 | ? | TRAINING |
| 42 | EEFF Baika S.A. 31-12-2018 individual.pdf | eeff_auditados | -1 | ? | TRAINING |
| 43 | EEFF IFRS Vitapro 2017.pdf | eeff_auditados | -1 | ? | TRAINING |
| 44 | EEFF Inmobiliaria LA Ltda. al 31 de dic. 2017.pdf | eeff_auditados | -1 | ? | TRAINING |
| 45 | EEFF PNV S.A. 31-12-2018.pdf | eeff_auditados | -1 | ? | TRAINING |
| 46 | EEFF SJF S.A. 31-12-2018 individual..pdf | eeff_auditados | -1 | ? | TRAINING |
| 47 | EEFF SJF y filiales consolidado 31 03 2019.pdf | eeff_auditados | -1 | ? | TRAINING |
| 48 | EEFF T y G Vecchiola 2016-2015.pdf | eeff_auditados | -1 | ? | TRAINING |
| 49 | EEFF Temporada 2018-2017 A  El Comino.pdf | eeff_auditados | -1 | ? | TRAINING |
| 50 | EEFF Temporada 2018-2017 A  Santa Amelia.pdf | eeff_auditados | -1 | ? | TRAINING |
| 51 | EEFF VDS S.A. 31-12-2018 consolidado..pdf | eeff_auditados | -1 | ? | TRAINING |
| 52 | EEFF VDS S.A. 31-12-2018 individual..pdf | eeff_auditados | -1 | ? | TRAINING |
| 53 | EEFF preliminar TyG DIC_2016.pdf | eeff_auditados | -1 | ? | TRAINING |
| 54 | EEFF_TRAF_2016.pdf | eeff_auditados | -1 | ? | TRAINING |
| 55 | EERR AICSA 2019.pdf | resultados | -1 | ? | STRESS |
| 56 | EERR CENTRAL 2019.pdf | resultados | -1 | ? | STRESS |
| 57 | EERR INMOBILIARIA 2019.pdf | resultados | -1 | ? | STRESS |
| 58 | EERR MEGAMERCADOS 2019.pdf | resultados | -1 | ? | STRESS |
| 59 | EERR SUPER CUGAT 2019.pdf | resultados | -1 | ? | STRESS |
| 60 | consolidado sept.pdf | consolidado | -1 | ? | STRESS |
| 61 | consolidado torca 15 y 16.pdf | consolidado | -1 | ? | STRESS |

## Formatos Completamente Nuevos

**17 archivos** presentan estructuras no registradas previamente en el sistema.

### Familia: anexo_activo_fijo (2 archivos)

**¿Qué lo hace diferente?**

- No son balances generales — son Anexos de Activo Fijo (PP&E)
- Estructura de tabla con columnas: Valor Bruto, Depreciación Acumulada, Valor Neto
- Organizado por tipo de activo (terrenos, edificios, maquinarias, vehículos, etc.)
- Pueden o no tener códigos de cuenta estándar

**Parser recomendado:** Puede adaptarse desde el parser universal con un layout custom. La estructura es tabular y las columnas numéricas son regulares. Se necesita un layout detector especializado para tablas de activo fijo.

| Archivo | Empresa | Año | Págs | Cuentas | Código | OCR | Headers | Categoría |
|---------|---------|-----|------|---------|--------|-----|---------|-----------|
| Anexo 1 ACT FIJO MEGAMERCADOS 2019.pdf | Anexo 1 ACT FIJ | 2019 | 2 | 94 | sin_codigo | N | activo | HOLDOUT |
| Anexo 1 ACT FIJO SOC SUPERMERCADOS 2019.pdf | Anexo 1 ACT FIJ | 2019 | 1 | 19 | sin_codigo | N | activo,activo | STRESS |

### Familia: cpt_tasacion (5 archivos)

**¿Qué lo hace diferente?**

- Certificados de Precios de Terreno (CPT)
- Estructura de datos catastrales y de tasación
- Generalmente 41 páginas con información de múltiples propiedades

**Parser recomendado:** Requiere parser nuevo o integración con parser de tasación. Similar a IT_*.

| Archivo | Empresa | Año | Págs | Cuentas | Código | OCR | Headers | Categoría |
|---------|---------|-----|------|---------|--------|-----|---------|-----------|
| CPTAgrGonzagriLtda.pdf | CPTAgrGonzagriL | None | 41 | -1 | ? | ? | ? | STRESS |
| CPTAgrGonzalezLtda.pdf | CPTAgrGonzalezL | None | 41 | -1 | ? | ? | ? | STRESS |
| CPTExportadora.pdf | CPTExportadora | None | 41 | -1 | ? | ? | ? | STRESS |
| CPTGonzagriS.A..pdf | CPTGonzagriS.A. | None | 41 | -1 | ? | ? | ? | STRESS |
| CPTVin¦âaFolatre.pdf | CPTVin¦âaFolat | None | 41 | -1 | ? | ? | ? | STRESS |

### Familia: informe_tasacion (8 archivos)

**¿Qué lo hace diferente?**

- Son informes de tasación de propiedades y activos (formato IT_)
- Contienen datos catastrales: rol de avalúo, superficie, metros cuadrados
- Valores de tasación fiscal y comercial
- Estructura completamente diferente a un balance contable

**Parser recomendado:** Requiere parser nuevo especializado en informes de tasación. No reutiliza el parser de balances.

| Archivo | Empresa | Año | Págs | Cuentas | Código | OCR | Headers | Categoría |
|---------|---------|-----|------|---------|--------|-----|---------|-----------|
| IT_0331_EL TRAPICHE_SABGRADA FAMILIA_TAS.pdf | IT 0331 EL TRAP | None | 26 | -1 | ? | ? | ? | STRESS |
| IT_0335_Gonzagri Ltda_79606270_Lisonjera 1-2 Bien  | IT 0335 Gonzagr | None | 8 | -1 | ? | ? | ? | STRESS |
| IT_0336_Lisonjera Lote 4_Packing_Yerbas Buenas_TAS | IT 0336 Lisonje | None | 21 | -1 | ? | ? | ? | STRESS |
| IT_0338_Gonzagri Ltda_79606270_Viena Pc 26 -33_35  | IT 0338 Gonzagr | None | 8 | -1 | ? | ? | ? | STRESS |
| IT_0340_Gonzagri Ltda_79606270_Buena Fe_Molina_TAS | IT 0340 Gonzagr | None | 8 | -1 | ? | ? | ? | STRESS |
| IT_0341_Gonzagri Ltda_79606270_Huemul_Teno_Chimbar | IT 0341 Gonzagr | None | 10 | -1 | ? | ? | ? | STRESS |
| IT_0342_Gonzagri Ltda_79606270_La Cruz Viluco_La P | IT 0342 Gonzagr | None | 8 | -1 | ? | ? | ? | STRESS |
| IT_0343_Teniente Cruz_Folatre_Teno_TAS INDUSTRIAL. | IT 0343 Tenient | None | 17 | -1 | ? | ? | ? | STRESS |

### Familia: notas_explicativas (2 archivos)

**¿Qué lo hace diferente?**

- Son notas explicativas a los EEFF, no balances
- Formato de texto narrativo con tablas embebidas
- Contienen políticas contables, desgloses, y revelaciones
- No contienen listados de cuentas contables estándar

**Parser recomendado:** No aplica. Estos documentos no deben procesarse como balances. Se recomienda excluirlos del pipeline de balance.

| Archivo | Empresa | Año | Págs | Cuentas | Código | OCR | Headers | Categoría |
|---------|---------|-----|------|---------|--------|-----|---------|-----------|
| Notas Explicativas Central 2019.pdf | Notas Explicati | 2019 | 52 | -1 | ? | ? | ? | REJECTED |
| Notas Explicativas Inmobiliaria 2019.pdf | Notas Explicati | 2019 | 48 | -1 | ? | ? | ? | REJECTED |

## Recomendaciones de Asignación

### TRAINING (19 archivos)

| Archivo | Cuentas | Familia | Estado |
|---------|---------|---------|--------|
| 2024- Pre_balance_Chilolac_2024 firmado.pdf | 232 | pre_balance | KNOWN_SUPPORTED |
| BALANCE 2016 AG E INM SAN FELIX.PDF | 229 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE 2016_43bfd7.pdf | 219 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE 2021 SANTA TERESA FIRMADO.pdf | 455 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE GENERAL 2024 REDESA SPA.pdf | 260 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE LOS LIRIOS + CAPITAL PROPIO.PDF | 398 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2023 Tributario DSI.pdf | 202 | tributario | KNOWN_SUPPORTED |
| Balance 31-12-2018.pdf | 296 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 31-12-2019.pdf | 318 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Agrícola Gonzagri Ltda.pdf | 632 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Agrícola González Ltda.pdf | 600 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Alto 31-12-2016 (2) (1).pdf | 203 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Exportadora Gonzagri.pdf | 631 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Gonzagri S.A.pdf | 212 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Tributario 2023 (2).pdf | 310 | tributario | KNOWN_SUPPORTED |
| Balance Tributario DSI 2024.pdf | 209 | tributario | KNOWN_SUPPORTED |
| Balance Viña Folatre.pdf | 609 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance y EEFF -2023.pdf | 550 | eeff_completo | PARTIALLY_SUPPORTED |
| Balances Grupo.pdf | 2268 | eeff_completo | PARTIALLY_SUPPORTED |

### HOLDOUT (88 archivos)

| Archivo | Cuentas | Familia | Estado |
|---------|---------|---------|--------|
| 1.- BCE TRIBUTARIO 2021 INGEFIRE SpA.pdf | 103 | tributario | KNOWN_SUPPORTED |
| 10.2023 BALANCE INVERSIONES PD.pdf | 94 | balance_estandar | KNOWN_SUPPORTED |
| 10.2023 BALANCE POWER PRO.pdf | 82 | balance_estandar | KNOWN_SUPPORTED |
| 10.2023 BALANCE RUTA RENTAL.pdf | 73 | balance_estandar | KNOWN_SUPPORTED |
| 2022 Balance Firmado Geslog.pdf | 126 | balance_estandar | KNOWN_SUPPORTED |
| 3.- BCE TRIBUTARIO 2023 INGEFIRE SpA.pdf | 147 | tributario | KNOWN_SUPPORTED |
| 7.- BCE TRIBUTARIO 2024 INGEFIRE SpA (1).pdf | 126 | tributario | KNOWN_SUPPORTED |
| Anexo 1 ACT FIJO MEGAMERCADOS 2019.pdf | 94 | anexo_activo_fijo | NEW_FORMAT |
| BALANCE 2016 AG E INM EL DAIN.PDF | 161 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE 2020 Regional SpA 26.04.22.pdf | 196 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE EL DAIN 2014-2015.pdf | 178 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE GENERAL 2023 REDESA SPA.pdf | 109 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE GENERAL 2023 SOC. DE INVERSIONES UNIDEPRO S.A.. | 70 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE GENERAL 2024 SOC. DE INVERSIONES UNIDEPRO S.A.. | 121 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE PORT 2021.pdf | 85 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE SAN FELIX 2014-2015.pdf | 166 | eeff_completo | PARTIALLY_SUPPORTED |
| BALANCE TRIBUTARIO INMOBILIARIA DICIEMBRE 2023 firmado. | 150 | tributario | KNOWN_SUPPORTED |
| Balance  Port  2022 final.pdf | 91 | balance_estandar | KNOWN_SUPPORTED |
| Balance  individual Agricola La Viñita 2018.pdf | 86 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2014 Com San Ignaco Ltda.pdf | 72 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2014 Lacteos SI.pdf | 102 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2015 - Abad Garcia y Pons Ltda.pdf | 182 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2015 - Comercial Asturias Ltda.pdf | 159 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2015 - Soc Com e Inv La Santina SA.pdf | 153 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2015 - Soc de Inv Campomanes SA.pdf | 111 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2015 Agroexportaciones Chile S A .pdf | 101 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2015 Lacteos San Ignacio Limitada.pdf | 109 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2016 Campoamor S A .pdf | 104 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2016 La Santina S A .pdf | 103 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2016 Transportes Libardom Ltda .pdf | 72 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2016.pdf | 152 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2017 - Mar Vivo.pdf | 62 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2017 Agricola el Jardin.pdf | 94 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2017.pdf | 165 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2018 Agricola el Jardin.pdf | 123 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2018 con firma.pdf | 177 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2020 Istria.pdf | 69 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2020 Maestranza.pdf | 78 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2021 Istria SA.pdf | 77 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2021 Maestranza.pdf | 82 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2022 Istria SA.pdf | 69 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2022 Maestranza.pdf | 91 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2023 Central.pdf | 161 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance 2023 Istria SA.pdf | 61 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2023 Maestranza.pdf | 78 | balance_estandar | KNOWN_SUPPORTED |
| Balance AGRICLA EL RINCON DE ÑILHUE S.A. 7-2-18.pdf | 74 | balance_estandar | KNOWN_SUPPORTED |
| Balance Agricola El Carmelo dic 2018.pdf | 87 | balance_estandar | KNOWN_SUPPORTED |
| Balance Agricola El Dain Ltda 2013.pdf | 89 | balance_estandar | KNOWN_SUPPORTED |
| Balance Agricola San Felix S A  2011 2012.pdf | 164 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Agricola San Felix S A  2013.pdf | 89 | balance_estandar | KNOWN_SUPPORTED |
| Balance Agricola el Jardin Año 2019 (3).pdf | 153 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Agroex 2014.pdf | 86 | balance_estandar | KNOWN_SUPPORTED |
| Balance Architec 2020 (Firmado).pdf | 82 | balance_estandar | KNOWN_SUPPORTED |
| Balance Architec 2021 (Firmado).pdf | 76 | balance_estandar | KNOWN_SUPPORTED |
| Balance Architec 2022 (Firmado).pdf | 75 | balance_estandar | KNOWN_SUPPORTED |
| Balance El Dain 2016.pdf | 160 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Esperanza 2020 (Firmado).pdf | 87 | balance_estandar | KNOWN_SUPPORTED |
| Balance Esperanza 2020 (Firmado)_e8457b.pdf | 138 | balance_estandar | KNOWN_SUPPORTED |
| Balance Esperanza 2021 (Firmado).pdf | 110 | balance_estandar | KNOWN_SUPPORTED |
| Balance Esperanza 2022 (Firmado).pdf | 107 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frio 2020 (Firmado).pdf | 73 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frio 2021 (Firmado).pdf | 78 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frio 2022 (Firmado).pdf | 72 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frutera 2020 (Firmado).pdf | 140 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frutera 2021 (Firmado).pdf | 146 | balance_estandar | KNOWN_SUPPORTED |
| Balance Frutera 2022 (Firmado).pdf | 150 | balance_estandar | KNOWN_SUPPORTED |
| Balance General 2023.pdf | 61 | balance_estandar | KNOWN_SUPPORTED |
| Balance General al 31 de diciembre 2023 - Regional Spa. | 191 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance General final año 2022 - Regional Spa.pdf | 187 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance Los Robles 2020 (Firmado).pdf | 65 | balance_estandar | KNOWN_SUPPORTED |
| Balance Los Robles 2021 (Firmado).pdf | 71 | balance_estandar | KNOWN_SUPPORTED |
| Balance Los Robles 2022 (Firmado).pdf | 69 | balance_estandar | KNOWN_SUPPORTED |
| Balance TE 12-2023.pdf | 135 | balance_estandar | KNOWN_SUPPORTED |
| Balance Tributario 2022 Wilug Minería SpA.pdf | 100 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2015 - Firmados.pd | 78 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2016 de CyH, firma | 89 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2016, Soc. Inmob.  | 64 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2016, Soc. de Inv. | 62 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2017, Maq. Ag. CyH | 99 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2017, Serv. y Neg. | 119 | tributario | KNOWN_SUPPORTED |
| Balance agricola 2023.pdf | 128 | balance_estandar | KNOWN_SUPPORTED |
| Balance división al 31 de Agosto ( Inversiones San Ign | 66 | balance_estandar | KNOWN_SUPPORTED |
| Balance inmobiliaria 2023.pdf | 128 | balance_estandar | KNOWN_SUPPORTED |
| Balance ryc 2023.pdf | 191 | eeff_completo | PARTIALLY_SUPPORTED |
| Balance y EERR Exportadora Agua Santa  (USD) 31-12-2017 | 76 | resultados | PARTIALLY_SUPPORTED |
| BalanceDic2018.pdf | 99 | balance_estandar | KNOWN_SUPPORTED |
| Balances 2015-2014 Inmobiliaria Vecchiola.pdf | 113 | balance_estandar | KNOWN_SUPPORTED |
| Balances 2015-2014 Inversiones  Vecchiola.pdf | 119 | balance_estandar | KNOWN_SUPPORTED |

### STRESS (27 archivos)

| Archivo | Cuentas | Familia | Estado |
|---------|---------|---------|--------|
| 8_balance_tributario_CREDISR_2022.pdf | 49 | tributario | KNOWN_SUPPORTED |
| Anexo 1 ACT FIJO SOC SUPERMERCADOS 2019.pdf | 19 | anexo_activo_fijo | NEW_FORMAT |
| BALANCE CORREGIDO SAN FELIX 2015 hoja 1.pdf | 52 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE CORREGIDO SAN FELIX 2015 hoja 2.pdf | 37 | balance_simple | KNOWN_SUPPORTED |
| BALANCE DAIN 2015 hoja 1.pdf | 52 | balance_estandar | KNOWN_SUPPORTED |
| BALANCE DAIN 2015 hoja 2 (2).pdf | 31 | balance_simple | KNOWN_SUPPORTED |
| BALANCE DALMACIA 1 2016.pdf | 35 | balance_simple | KNOWN_SUPPORTED |
| BALANCE DALMACIA 2 2016.pdf | 38 | balance_simple | KNOWN_SUPPORTED |
| Balance 12_2015.pdf | 27 | balance_simple | KNOWN_SUPPORTED |
| Balance 2017 - Inversiones Línea Real.pdf | 27 | balance_simple | KNOWN_SUPPORTED |
| Balance 2022 Ingenieria.pdf | 41 | balance_simple | KNOWN_SUPPORTED |
| Balance 2022 Maquinas.pdf | 47 | balance_simple | KNOWN_SUPPORTED |
| Balance 2022 Transp Istria.pdf | 38 | balance_simple | KNOWN_SUPPORTED |
| Balance 2023 Ingenieria.pdf | 40 | balance_simple | KNOWN_SUPPORTED |
| Balance 2023 Maquinas.pdf | 57 | balance_estandar | KNOWN_SUPPORTED |
| Balance 2023 Mega.pdf | 12 | balance_simple | KNOWN_SUPPORTED |
| Balance Asipac 2015.pdf | 14 | balance_simple | KNOWN_SUPPORTED |
| Balance Clinica Hyperbaric 2025.pdf | 29 | balance_simple | KNOWN_SUPPORTED |
| Balance Inmob 2015.pdf | 11 | balance_simple | KNOWN_SUPPORTED |
| Balance Mega 2015.pdf | 16 | balance_simple | KNOWN_SUPPORTED |
| Balance Sup Central 2015.pdf | 15 | balance_simple | KNOWN_SUPPORTED |
| Balance Tributario 2022 Claps Firmado.pdf | 55 | tributario | KNOWN_SUPPORTED |
| Balance Tributario Chemo S.A Dic.2020.pdf | 23 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2017, Inm. Indepen | 30 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2017, Inv. e Inmob | 36 | tributario | KNOWN_SUPPORTED |
| Balance Tributario a diciembre 31 de 2017, Min. La Rubi | 57 | tributario | KNOWN_SUPPORTED |
| Balance al 31-12-2019 Puerta del Barro.pdf | 51 | balance_estandar | KNOWN_SUPPORTED |

### REJECTED (7 archivos)

| Archivo | Motivo |
|---------|--------|
| BALANCE 2017 G FUTURO.PDF | Sin cuentas (o no procesado) |
| BALANCE 2017 LI Y CHAN.PDF | Sin cuentas (o no procesado) |
| BALANCE 2021 Regional SpA 26.04.22.pdf | Sin cuentas (o no procesado) |
| Balance 2019 FIRMADO.pdf | Sin cuentas (o no procesado) |
| Balance General Año 2016 firmado.pdf | Sin cuentas (o no procesado) |
| Notas Explicativas Central 2019.pdf | Not processed |
| Notas Explicativas Inmobiliaria 2019.pdf | Not processed |

## Recomendaciones de Parser por Familia

| Familia | Archivos | Parser | Acción Requerida |
|---------|----------|--------|-----------------|
| balance_estandar (100) | ParserPDF (universal) | Soportado — sin cambios |
| pre_balance (33) | ParserPDF (universal) | Soportado — sin cambios |
| eeff_completo (32) | ParserPDF + segmentación | Parcial — mejorar multi-sección |
| tributario (24) | ParserPDF (universal) | Soportado — sin cambios |
| eeff_auditados (20) | ParserPDF + segmentación | Parcial — mejorar multi-sección |
| balance_simple (16) | ParserPDF (universal) | Soportado — sin cambios |
| informe_tasacion (8) | Nuevo parser | Parser especializado en tasaciones |
| resultados (6) | ParserPDF + segmentación | Parcial — mejorar detección EERR |
| desconocido (5) | Evaluar | Formato indeterminado — requiere revisión |
| cpt_tasacion (5) | Nuevo parser | Parser especializado en CPT tasaciones |
| consolidado (3) | ParserPDF (universal) | Soportado — validar multi-empresa |
| anexo_activo_fijo (2) | ParserPDF + layout custom | Adaptable — tabla activo fijo |
| notas_explicativas (2) | No aplica | No procesar — notas de texto |

## Resumen de Nuevos Formatos Detectados

| Formato | Archivos | Descripción | Acción |
|---------|----------|-------------|--------|
| **Anexo Activo Fijo** | 2 | Tablas de propiedad, planta y equipo con detalle de depreciación | Adaptar parser universal con layout custom |
| **Notas Explicativas EEFF** | 2 | Texto narrativo con políticas contables y desgloses | No procesar (excluir del pipeline) |
| **Informes Tasación (IT_)** | 3 | Tasación de propiedades: roles, avalúos, superficies | Requiere parser nuevo especializado |
| **Certificados CPT** | 5 | Certificados de Precios de Terreno (41 págs c/u) | Requiere parser nuevo especializado |

## Acciones Recomendadas

1. **Mover a TRAINING** — archivos con >200 cuentas de formatos soportados/parciales
2. **Mover a HOLDOUT** — archivos con 60-200 cuentas de formatos conocidos
3. **Mover a STRESS** — archivos con <60 cuentas o formatos a probar
4. **REJECTED** — archivos corruptos, vacíos, notas explicativas
5. **Archivos no procesados** (~200) requieren ejecución batch nocturna para completar análisis
6. **Evaluar parser de tasaciones** — IT_* y CPT* requieren parser nuevo (formato diferente)
7. **Anexos activo fijo** — requieren layout detector especializado para tablas PP&E
8. **Mejorar segmentación** — EEFF completos mezclan balance + resultados + notas en una sola lista

---

*Reporte generado automáticamente por Sprint 17 — INBOX Format Analysis*