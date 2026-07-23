# Reporte de Métricas por Documento

**Documentos evaluados:** 186
**Fecha:** 2026-07-09 19:15:29

---

## Resumen Global

| Métrica | Media | Mediana | Mín | Máx |
|---------|-------|---------|-----|-----|
| Confianza de Layout | 0.610 | 0.600 | 0.100 | 1.000 |
| Confianza OCR | 0.778 | 0.950 | 0.500 | 1.000 |
| Confianza del Parser | 0.431 | 0.500 | 0.000 | 0.800 |
| Confianza de Mapeo de Columnas | 0.470 | 0.350 | 0.000 | 1.000 |
| Calidad de Encabezados | 0.543 | 0.600 | 0.000 | 1.000 |
| Tasa de Aceptación de Candidatos | 0.354 | 0.342 | 0.000 | 0.918 |
| Tasa de Contaminación | 0.172 | 0.128 | 0.000 | 1.000 |

---

## Distribución por Grupo

### edge_cases (97 documentos)

| Métrica | Media | Mediana |
|---------|-------|---------|
| Confianza de Layout | 0.384 | 0.450 |
| Confianza OCR | 0.767 | 0.950 |
| Confianza del Parser | 0.402 | 0.500 |
| Confianza de Mapeo de Columnas | 0.252 | 0.300 |
| Calidad de Encabezados | 0.471 | 0.600 |
| Tasa de Aceptación de Candidatos | 0.308 | 0.315 |
| Tasa de Contaminación | 0.177 | 0.154 |

### validacion (89 documentos)

| Métrica | Media | Mediana |
|---------|-------|---------|
| Confianza de Layout | 0.857 | 1.000 |
| Confianza OCR | 0.791 | 0.950 |
| Confianza del Parser | 0.462 | 0.800 |
| Confianza de Mapeo de Columnas | 0.708 | 0.950 |
| Calidad de Encabezados | 0.621 | 1.000 |
| Tasa de Aceptación de Candidatos | 0.404 | 0.525 |
| Tasa de Contaminación | 0.168 | 0.120 |

---

## Distribución por Tipo de Archivo

### pdf (162 documentos)

| Métrica | Media | Mediana |
|---------|-------|---------|
| Confianza de Layout | 0.614 | 0.600 |
| Confianza OCR | 0.746 | 0.950 |
| Confianza del Parser | 0.494 | 0.500 |
| Confianza de Mapeo de Columnas | 0.470 | 0.350 |
| Calidad de Encabezados | 0.623 | 0.600 |
| Tasa de Aceptación de Candidatos | 0.407 | 0.419 |
| Tasa de Contaminación | 0.174 | 0.128 |

### xls (1 documentos)

| Métrica | Media | Mediana |
|---------|-------|---------|
| Confianza de Layout | 0.900 | 0.900 |
| Confianza OCR | 1.000 | 1.000 |
| Confianza del Parser | 0.000 | 0.000 |
| Confianza de Mapeo de Columnas | 0.750 | 0.750 |
| Calidad de Encabezados | 0.000 | 0.000 |
| Tasa de Aceptación de Candidatos | 0.000 | 0.000 |
| Tasa de Contaminación | 0.000 | 0.000 |

### xlsx (23 documentos)

| Métrica | Media | Mediana |
|---------|-------|---------|
| Confianza de Layout | 0.570 | 0.500 |
| Confianza OCR | 1.000 | 1.000 |
| Confianza del Parser | 0.000 | 0.000 |
| Confianza de Mapeo de Columnas | 0.461 | 0.400 |
| Calidad de Encabezados | 0.000 | 0.000 |
| Tasa de Aceptación de Candidatos | 0.000 | 0.000 |
| Tasa de Contaminación | 0.168 | 0.118 |

---

## Detalle por Documento

| Archivo | Grupo | Tipo | Layout | OCR | Parser | ColMapping | Header | AcceptRate | Contam |
|---------|-------|------|-------|-----|--------|------------|--------|------------|--------|
| 2018 01 15 Balance OPE simplificado.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.80 | 0.15 | 0.60 | 0.50 | 0.12 |
| BALANCE 2016.pdf | validaci | pdf | 0.85 | 0.95 | 0.80 | 0.95 | 0.90 | 0.92 | 0.03 |
| BALANCE CLASIFICADO 2016, Alto Jardin SA.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.49 | 0.24 |
| BALANCE CLASIFICADO AICSA 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.20 | 0.00 | 0.60 | 0.13 | 0.12 |
| BALANCE CLASIFICADO CENTRAL 2019.pdf | edge_cas | pdf | 0.20 | 0.95 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| BALANCE CLASIFICADO INMOBILIARIA 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.30 | 0.00 | 0.60 | 0.25 | 0.12 |
| BALANCE CLASIFICADO MEGAMERCADOS 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.30 | 0.00 | 0.60 | 0.22 | 0.13 |
| BALANCE CLASIFICADO SUPER CUGAT 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.20 | 0.00 | 0.60 | 0.16 | 0.14 |
| BALANCE CORREGIDO SAN FELIX 2015 hoja 1.pdf | validaci | pdf | 0.65 | 0.50 | 0.80 | 0.60 | 1.00 | 0.55 | 0.02 |
| BALANCE CORREGIDO SAN FELIX 2015 hoja 2.pdf | validaci | pdf | 1.00 | 0.50 | 0.50 | 0.80 | 1.00 | 0.44 | 0.08 |
| BALANCE DAIN 2015 hoja 1.pdf | validaci | pdf | 0.65 | 0.50 | 0.50 | 0.50 | 0.60 | 0.43 | 0.00 |
| BALANCE DAIN 2015 hoja 2 (2).pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.19 | 0.00 |
| BALANCE DALMACIA 1 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.54 | 0.16 |
| BALANCE DALMACIA 2 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.60 | 0.12 |
| BALANCE DENHAM.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.85 | 0.03 |
| BALANCE DENHAM_120.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.85 | 0.03 |
| BALANCE EL DAIN 2014-2015.pdf | validaci | pdf | 0.65 | 0.50 | 0.20 | 0.35 | 0.60 | 0.17 | 0.04 |
| BALANCE G. COMERCIALIZADORA 09.2016.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.03 |
| BALANCE GENERAL AGRICOLA 09.2016.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.04 |
| BALANCE GENERAL AGRICOLA 2013.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.04 |
| BALANCE GENERAL AGRICOLA 2014.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.05 |
| BALANCE GENERAL AGRICOLA 2015 (1).xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.04 |
| BALANCE ORIGINAL 2014.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.25 | 1.00 | 0.68 | 0.07 |
| BALANCE SAN FELIX 2014-2015.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.14 | 0.04 |
| Balance  individual Agricola La Viñita 2018.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.75 | 0.09 |
| Balance 12_2015.pdf | edge_cas | pdf | 0.20 | 0.95 | 0.80 | 0.05 | 0.00 | 0.63 | 0.15 |
| Balance 2014 Com San Ignaco Ltda.pdf | validaci | pdf | 1.00 | 0.95 | 0.00 | 0.80 | 1.00 | 0.04 | 0.25 |
| Balance 2014 Lacteos SI.pdf | validaci | pdf | 1.00 | 0.95 | 0.00 | 0.80 | 1.00 | 0.03 | 0.25 |
| Balance 2015 - Abad Garcia y Pons Ltda.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.45 | 0.05 |
| Balance 2015 - Comercial Asturias Ltda.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.50 | 0.35 | 0.60 | 0.46 | 0.06 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.40 | 0.05 |
| Balance 2015 - Soc Com e Inv La Santina SA.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.39 | 0.09 |
| Balance 2015 - Soc de Inv Campomanes SA.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.30 | 0.00 | 0.60 | 0.29 | 0.05 |
| Balance 2015 - Transp Libardon Ltda.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.33 | 0.09 |
| Balance 2015 Agroexportaciones Chile S A .pdf | validaci | pdf | 1.00 | 0.95 | 0.00 | 0.80 | 1.00 | 0.04 | 0.22 |
| Balance 2015 Lacteos San Ignacio Limitada.pdf | validaci | pdf | 1.00 | 0.95 | 0.00 | 0.80 | 1.00 | 0.03 | 0.24 |
| Balance 2016 Abad Garcia y Pons.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.30 | 0.60 | 0.71 | 0.07 |
| Balance 2016 Asturias Ltda .pdf | edge_cas | pdf | 0.45 | 0.50 | 0.80 | 0.35 | 0.60 | 0.60 | 0.10 |
| Balance 2016 Campoamor S A .pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.30 | 0.60 | 0.66 | 0.11 |
| Balance 2016 Campomanes S A .pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.52 | 0.15 |
| Balance 2016 La Santina S A .pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.65 | 0.11 |
| Balance 2016 Transportes Libardom Ltda .pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.50 | 0.12 |
| Balance 2017 - Frigorífco Santa Cruz.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.80 | 0.45 | 0.90 | 0.64 | 0.21 |
| Balance 2017 - Igesur.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.45 | 0.90 | 0.49 | 0.32 |
| Balance 2017 - Inversiones Línea Real.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.66 | 0.17 |
| Balance 2017 - Inversiones Santa Adriana.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.82 | 0.03 |
| Balance 2017 - Mar Vivo.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.31 | 0.16 |
| Balance 2017 - Naviera Orca.pdf | edge_cas | pdf | 0.20 | 0.95 | 0.50 | 0.00 | 0.00 | 0.31 | 0.13 |
| Balance 2017 Agricola el Jardin.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.75 | 0.10 |
| Balance 2017.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.61 | 0.12 |
| Balance 2018 Agricola el Jardin.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.84 | 0.07 |
| Balance 2018 con firma.pdf | edge_cas | pdf | 0.65 | 0.50 | 0.00 | 0.45 | 1.00 | 0.07 | 0.02 |
| Balance 2019 FIRMADO.pdf | edge_cas | pdf | 0.10 | 0.60 | 0.00 | 0.20 | 0.00 | 0.00 | 1.00 |
| Balance 2020.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.81 | 0.04 |
| Balance 31-12-2018.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.82 | 0.09 |
| Balance 31-12-2019.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.81 | 0.08 |
| Balance AGRICLA EL RINCON DE ÑILHUE S.A. 7-2-18.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.32 | 0.08 |
| Balance Agricola El Carmelo dic 2018.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.30 | 0.00 | 0.60 | 0.25 | 0.19 |
| Balance Agricola El Comino dic 2018.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.36 | 0.20 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | edge_cas | pdf | 0.65 | 0.50 | 0.80 | 0.60 | 1.00 | 0.58 | 0.05 |
| Balance Agricola El Dain Ltda 2013.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.67 | 0.03 |
| Balance Agricola San Felix S A  2011 2012.pdf | validaci | pdf | 1.00 | 0.50 | 0.50 | 0.95 | 1.00 | 0.43 | 0.05 |
| Balance Agricola San Felix S A  2013.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.53 | 0.07 |
| Balance Agricola Santa Amelia dic 2018.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.30 | 0.20 | 0.60 | 0.28 | 0.20 |
| Balance Agricola el Jardin Año 2019 (3).pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.79 | 0.09 |
| Balance Agrícola Gonzagri Ltda.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Agrícola Gonzagri Ltda_147.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Agrícola Gonzagri Ltda_149.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Agrícola González Ltda.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Agrícola González Ltda_150.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Agrícola González Ltda_153.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Agroex 2014.pdf | validaci | pdf | 1.00 | 0.95 | 0.00 | 0.80 | 1.00 | 0.03 | 0.22 |
| Balance Alto 31-12-2016 (2) (1).pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.65 | 0.08 |
| Balance Alto 31-12-2016 (2).pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.65 | 0.08 |
| Balance Asipac 2015.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.12 | 0.19 |
| Balance Bosque Playa Cachagua 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.80 | 0.15 | 0.60 | 0.55 | 0.19 |
| Balance CONSOLIDADO HOLDING 122017.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.74 | 0.05 |
| Balance Capiro 2017-2018.pdf | edge_cas | pdf | 0.20 | 0.50 | 0.80 | 0.05 | 0.00 | 0.58 | 0.10 |
| Balance Chillan.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.44 |
| Balance Clasificado 2016.pdf | edge_cas | pdf | 0.20 | 0.50 | 0.20 | 0.00 | 0.00 | 0.16 | 0.02 |
| Balance Clasificado JGTc 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.80 | 0.15 | 0.60 | 0.64 | 0.08 |
| Balance Clasificado Mar 2016 Vecchiola.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.50 | 0.45 | 0.90 | 0.48 | 0.11 |
| Balance Clasificado RGTc 2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.80 | 0.15 | 0.60 | 0.60 | 0.08 |
| Balance Clasificado y Estado de Resultados año 2018 fi | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.40 | 0.09 |
| Balance Clasificado y Estado resultado 2017 Inversiones | edge_cas | pdf | 0.25 | 0.50 | 0.30 | 0.15 | 0.60 | 0.29 | 0.23 |
| Balance Consolidado Grupo Alto 31-12-2016 (1).pdf | validaci | pdf | 0.75 | 0.95 | 0.80 | 0.65 | 0.60 | 0.61 | 0.14 |
| Balance El Dain 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.54 | 0.09 |
| Balance Exportadora Agua Santa dic 2018.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.30 | 0.20 | 0.60 | 0.28 | 0.22 |
| Balance Exportadora Gonzagri.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Exportadora Gonzagri_155.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Exportadora Gonzagri_157.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance General Año 2016 firmado.pdf | edge_cas | pdf | 0.10 | 0.60 | 0.00 | 0.20 | 0.00 | 0.00 | 1.00 |
| Balance General SA JAHUEL 2020 V3.pdf | edge_cas | pdf | 0.65 | 0.95 | 0.50 | 0.45 | 1.00 | 0.38 | 0.27 |
| Balance Gonzagri S.A.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Gonzagri S.A_154.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Gonzagri S.A_156.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.40 |
| Balance Inmob 2015.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.15 | 0.23 |
| Balance Mega 2015.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.11 | 0.17 |
| Balance Prelimiar C&H Jul.2018 BANCOS.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.07 |
| Balance Prelimiar C&H May.2017.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.07 |
| Balance Prelimiar C&H May.2017_100.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.07 |
| Balance Prelimiar C&H May.2018 BANCOS.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.07 |
| Balance Sup Central 2015.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.11 | 0.17 |
| Balance Tributario Chemo S.A Dic.2020.pdf | edge_cas | pdf | 0.20 | 0.50 | 0.50 | 0.00 | 0.00 | 0.38 | 0.08 |
| Balance Tributario a diciembre 31 de 2015 - Firmados.pd | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.65 | 0.12 |
| Balance Tributario a diciembre 31 de 2016 de CyH, firma | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.67 | 0.11 |
| Balance Tributario a diciembre 31 de 2016, Soc. Inmob.  | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.54 | 0.13 |
| Balance Tributario a diciembre 31 de 2016, Soc. de Inv. | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.56 | 0.18 |
| Balance Tributario a diciembre 31 de 2017, Inm. Indepen | edge_cas | pdf | 0.65 | 0.50 | 0.80 | 0.60 | 1.00 | 0.55 | 0.12 |
| Balance Tributario a diciembre 31 de 2017, Inv. e Inmob | edge_cas | pdf | 0.65 | 0.50 | 0.80 | 0.60 | 1.00 | 0.53 | 0.16 |
| Balance Tributario a diciembre 31 de 2017, Maq. Ag. CyH | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.73 | 0.11 |
| Balance Tributario a diciembre 31 de 2017, Min. La Rubi | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.56 | 0.17 |
| Balance Tributario a diciembre 31 de 2017, Serv. y Neg. | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.73 | 0.13 |
| Balance Vecchiola Dic_2016.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.80 | 0.45 | 0.90 | 0.51 | 0.12 |
| Balance Viña Folatre.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Viña Folatre_146.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Viña Folatre_148.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.00 | 0.41 |
| Balance Xpovin.pdf | edge_cas | pdf | 0.20 | 0.95 | 0.00 | 0.00 | 0.00 | 0.03 | 0.60 |
| Balance al 31-12-2019 Puerta del Barro.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.63 | 0.10 |
| Balance clasificado junio 2016 Vecchiola.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.80 | 0.45 | 0.90 | 0.54 | 0.13 |
| Balance clinica el Loa.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.26 |
| Balance de 8 columnas firmado año 2018.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.10 | 0.01 |
| Balance división al 31 de Agosto ( Inversiones San Ign | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.58 | 0.06 |
| Balance y EERR Exportadora Agua Santa  (USD) 31-12-2017 | edge_cas | pdf | 0.45 | 0.50 | 0.30 | 0.20 | 0.60 | 0.25 | 0.23 |
| BalanceDic2018.pdf | validaci | pdf | 1.00 | 0.95 | 0.50 | 0.80 | 1.00 | 0.49 | 0.17 |
| Balances 2015-2014 Inmobiliaria Vecchiola.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.32 | 0.32 |
| Balances 2015-2014 Inversiones  Vecchiola.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.00 | 0.60 | 0.32 | 0.30 |
| Balances tuniche explicacionxlsx.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.34 |
| ECDS Balance 10-2020 (1).pdf | edge_cas | pdf | 0.35 | 0.95 | 0.80 | 0.30 | 0.60 | 0.71 | 0.05 |
| EEFF - 2017 Alto Pelarco.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.37 | 0.21 |
| EEFF - 2017 El Estero.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.28 | 0.20 |
| EEFF - 2017 La Esperanza.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.28 | 0.20 |
| EEFF - 2017 Las Loicas.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.31 | 0.20 |
| EEFF - 2017 Los Nogales.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.30 | 0.20 |
| EEFF - 2018 Alto Pelarco.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.26 | 0.21 |
| EEFF - 2018 El Estero.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.20 | 0.35 | 0.60 | 0.19 | 0.20 |
| EEFF - 2018 La Esperanza.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.31 | 0.20 |
| EEFF - 2018 Las Loicas.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.26 | 0.21 |
| EEFF - 2018 Los Nogales.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.30 | 0.21 |
| EEFF - 2019 Alto Pelarco.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.33 | 0.20 |
| EEFF - 2019 El Estero.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.31 | 0.20 |
| EEFF - 2019 La Esperanza.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.22 | 0.21 |
| EEFF - 2019 Las Loicas.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.50 | 0.35 | 0.60 | 0.31 | 0.20 |
| EEFF - 2019 Los Nogales.pdf | edge_cas | pdf | 0.45 | 0.95 | 0.30 | 0.35 | 0.60 | 0.26 | 0.20 |
| EEFF - Histórico (2).xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.33 |
| EEFF 12-2015 MV.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.50 | 0.00 | 0.60 | 0.44 | 0.26 |
| EEFF 16 - RENTAS 17 - GRUPO CASA GARCIA.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.50 | 0.15 | 0.60 | 0.44 | 0.06 |
| EEFF 2016 UPCOM.xls | validaci | xls | 0.90 | 1.00 | 0.00 | 0.75 | 0.00 | 0.00 | 0.00 |
| EEFF 2017 PreliminarSecurity.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.31 |
| EEFF 2018  Terra.pdf | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.60 | 0.13 |
| MFCB - Balance 2015 Nivel 3, firmado (27-07-2016) - Mul | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.53 | 0.12 |
| MFCB - Balance 2016 Nivel 3, firmado (16-05-2017) - Mul | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.53 | 0.12 |
| MFCB - Pre-Balance 2017 Oct.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.50 | 0.13 |
| MFCB -EEFF Historico y Proyectado.xlsx | validaci | xlsx | 0.90 | 1.00 | 0.00 | 0.75 | 0.00 | 0.00 | 0.14 |
| MFV -EEFF Historico y Proyectado.xlsx | validaci | xlsx | 0.90 | 1.00 | 0.00 | 0.75 | 0.00 | 0.00 | 0.28 |
| OPE BALANCE 2016.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.79 | 0.04 |
| PRE BALANCE 2018.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.60 | 0.12 |
| PRE BALANCE AGRICOLA SAN SEBASTIAN.pdf | validaci | pdf | 0.60 | 0.50 | 0.00 | 0.25 | 0.00 | 0.10 | 0.01 |
| PRE-BALANCES AICSA DICIEMBRE 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 0.95 | 1.00 | 0.61 | 0.09 |
| PRE-BALANCES INMOBILIARIA DICIEMBRE 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.82 | 0.03 |
| PRE-BALANCES MEGAMERCADOS DICIEMBRE 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.84 | 0.02 |
| PRE-BALANCES SUPER CUGAT DICIEMBRE 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.50 | 0.95 | 1.00 | 0.44 | 0.10 |
| Pre Balance Alto S.A. al 31-10-2017.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.74 | 0.05 |
| Pre Balance Emilio Kuncar 2017.pdf | validaci | pdf | 1.00 | 0.50 | 0.80 | 0.95 | 1.00 | 0.64 | 0.12 |
| Pre Balance Tributario CASA Dic 2019 v31.03.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 0.60 | 0.75 | 0.02 |
| Pre Balance Tributario VFCH Dic 2019 v31.03.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.79 | 0.01 |
| Pre Balances 2017.xlsx | validaci | xlsx | 0.90 | 1.00 | 0.00 | 0.75 | 0.00 | 0.00 | 0.30 |
| Pre- Balance Nov 2019 Agricola el Jardin.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.82 | 0.10 |
| Pre-Balance Comercializadora 2018.pdf | validaci | pdf | 0.60 | 0.50 | 0.20 | 0.25 | 0.00 | 0.12 | 0.00 |
| Pre-Balance Oscar Prohens Espinosa 2017.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.86 | 0.03 |
| Pre-Balance al 31-12-2020_TRANSPORTES JG_76350177-9 .xl | validaci | xlsx | 0.90 | 1.00 | 0.00 | 0.75 | 0.00 | 0.00 | 0.05 |
| Resumen Balance san Osvaldo 2018.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.36 |
| TWG y filial Balance presentación 2020-2019.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.50 | 0.15 | 0.60 | 0.41 | 0.20 |
| TWG y filial Balance presentación 2021-2020.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.50 | 0.15 | 0.60 | 0.41 | 0.20 |
| TWG y filial Balance presentación 2021-2020_312.pdf | edge_cas | pdf | 0.35 | 0.95 | 0.50 | 0.15 | 0.60 | 0.41 | 0.20 |
| balance Agricola 2019 definitivo.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.25 |
| balance CUC.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.21 |
| balance CUPM.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.12 |
| balance cm 2015.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.05 | 0.62 |
| balance cm 2016.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.09 | 0.65 |
| balance cm 2017.pdf | validaci | pdf | 0.60 | 0.95 | 0.00 | 0.25 | 0.00 | 0.02 | 0.55 |
| balance combinado El Comino dic 2018.pdf | edge_cas | pdf | 0.45 | 0.50 | 0.50 | 0.20 | 0.60 | 0.35 | 0.19 |
| balance general guayacan 2020.pdf | edge_cas | pdf | 0.65 | 0.95 | 0.50 | 0.45 | 1.00 | 0.35 | 0.28 |
| balance individual Agricola Cerrillos de Tamaya 2018.pd | edge_cas | pdf | 0.25 | 0.50 | 0.80 | 0.15 | 0.60 | 0.52 | 0.20 |
| balance tributario dic 2020 agr tuqui.xlsx | edge_cas | xlsx | 0.50 | 1.00 | 0.00 | 0.40 | 0.00 | 0.00 | 0.02 |
| pre-balance central 2016.pdf | validaci | pdf | 1.00 | 0.95 | 0.80 | 1.00 | 1.00 | 0.85 | 0.02 |

---

## Notas

- Cada métrica es independiente — **no existe un score compuesto**
- Las métricas no se usan para bloquear ni priorizar documentos
- `layout_confidence`: basada en grupo, compatibilidad con ULTIMAS_COLS, riesgo
- `ocr_confidence`: basada en tipo de archivo, si requirió OCR, ruido OCR
- `parser_confidence`: basada en tasa de clasificación y cuentas ignoradas
- `column_mapping_confidence`: basada en compatibilidad y origen desconocido de columnas
- `header_quality`: basada en número y tipo de encabezados detectados
- `candidate_accept_rate`: basada en aceptación del gatekeeper (fallback: clasificación)
- `contamination_rate`: basada en porcentaje de líneas de ruido sobre total de líneas