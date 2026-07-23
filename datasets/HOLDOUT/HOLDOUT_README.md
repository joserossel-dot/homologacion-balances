# DATASET_HOLDOUT

## Propósito

Conjunto de balances no utilizados para desarrollo de reglas, CMCC, 
diccionario ni variantes. Exclusivamente para benchmark del parser 
y evaluación de higiene/contaminación.

## Composición

- **Total archivos**: 20
- **Tamaño total**: 11133 KB
- **Cuentas totales**: 2717
- **Empresas distintas**: 18
- **Documentos OCR**: 0

## Archivos

| Archivo | Tamaño (KB) | Cuentas | Clasificadas | UNKNOWN | OCR |
|---------|------------|---------|-------------|---------|-----|
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | 98 | 168 | 67 | 57 | no |
| BALANCE ORIGINAL 2014.pdf | 412 | 371 | 252 | 224 | no |
| EEFF - 2018 Los Nogales.pdf | 428 | 54 | 16 | 15 | no |
| Balance Agricola El Comino dic 2018.pdf | 757 | 95 | 34 | 25 | no |
| Balance Xpovin.pdf | 4746 | 401 | 14 | 14 | no |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | 48 | 56 | 16 | 12 | no |
| Balance 2016 Campomanes S A .pdf | 398 | 65 | 34 | 25 | no |
| balance general guayacan 2020.pdf | 45 | 203 | 71 | 35 | no |
| Balance 2015 - Transp Libardon Ltda.pdf | 77 | 119 | 39 | 30 | no |
| BALANCE CLASIFICADO AICSA 2019.pdf | 684 | 102 | 13 | 11 | no |
| Balance 2016 Asturias Ltda .pdf | 579 | 102 | 61 | 50 | no |
| Balance Agricola Santa Amelia dic 2018.pdf | 761 | 100 | 28 | 23 | no |
| Balance General SA JAHUEL 2020 V3.pdf | 56 | 214 | 81 | 41 | no |
| Balance 2017 - Naviera Orca.pdf | 55 | 62 | 19 | 19 | no |
| Balance Exportadora Agua Santa dic 2018.pdf | 691 | 81 | 23 | 15 | no |
| Balance 2017 - Igesur.pdf | 23 | 37 | 18 | 14 | no |
| Balance Vecchiola Dic_2016.pdf | 135 | 41 | 21 | 19 | no |
| Balance 2016 Abad Garcia y Pons.pdf | 683 | 133 | 94 | 81 | no |
| Balance Capiro 2017-2018.pdf | 182 | 124 | 72 | 71 | no |
| Balance Agricola El Dain Ltda 2011 2012.pdf | 276 | 189 | 110 | 94 | no |

## Origen

Seleccionados de `datasets/edge_cases/`.

Criterios de selección:

1. Una empresa por archivo (máxima diversidad)
2. Variedad de años (2011–2020)
3. Variedad de cuentas totales (37–401)
4. Incluye OCR y texto nativo
5. Incluye layouts compatibles e incompatibles

## Restricciones

- Este dataset NO puede usarse para: entrenar reglas, descubrir variantes, 
  ampliar diccionario, ni modificar CMCC.
- Este dataset SÍ puede usarse para: benchmark del parser, benchmark de 
  higiene, benchmark de contaminación, evaluación de accuracy/precision/recall/F1.

## Empresas incluidas

- 2015
- 2016 Abad Garcia y Pons
- 2016 Asturias Ltda
- 2016 Campomanes S A
- 2017
- Agricola El Comino dic 2018
- Agricola El Dain Ltda 2011 2012
- Agricola Santa Amelia dic 2018
- CLASIFICADO AICSA 2019
- Capiro 2017
- Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda
- EEFF
- Exportadora Agua Santa dic 2018
- General SA JAHUEL 2020 V3
- ORIGINAL 2014
- Vecchiola Dic_2016
- Xpovin
- general guayacan 2020