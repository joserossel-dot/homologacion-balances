# Benchmark Summary — Certificación

**Fecha:** 2026-07-26
**Pipeline:** HomologationPipeline
**Dataset:** datasets/HOLDOUT/ (20 archivos)

---

## Métricas globales

| Métrica | Valor |
|---------|-------|
| Archivos procesados | 20 |
| Tiempo total | 175.653s |
| Tiempo promedio por archivo | 8.783s |
| Cuentas detectadas | 2692 |
| Cuentas homologadas | 1251 |
| Cuentas ignoradas (sin movimiento) | 1441 |
| Cuentas desconocidas (sin clasificar) | 1030 |
| Learning hits (Gold Standard) | 101 |
| Archivos con errores | 0 |
| Archivos con warnings | 0 |
| Precisión extracción promedio (confianza >= 0.7) | 16.19% |
| Precisión homologación promedio | 48.77% |
| Confianza promedio global | 0.1611 |

---

## Distribución de métodos de clasificación

| Método | Cuentas | % |
|--------|---------|---|
| code | 60 | 4.8% |
| dictionary_exact | 29 | 2.3% |
| dictionary_fuzzy | 22 | 1.8% |
| learning_exact | 84 | 6.7% |
| learning_fuzzy | 17 | 1.4% |
| regex | 9 | 0.7% |
| unclassified | 1030 | 82.3% |

---

## Resultados por archivo

| Archivo | Tiempo (s) | Detectadas | Homologadas | Ignoradas | Unknown | Learning Hits | Confianza Prom |
|---------|-----------|-----------|-------------|-----------|---------|--------------|--------------|
| BALANCE CLASIFICADO AICSA 2019.pdf | 1.114 | 101 | 20 | 81 | 18 | 2 | 0.098 |
| BALANCE ORIGINAL 2014.pdf | 27.766 | 371 | 255 | 116 | 224 | 17 | 0.1104 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | 13.656 | 168 | 69 | 99 | 59 | 8 | 0.138 |
| Balance 2015 - Transp Libardon Ltda.pdf | 10.901 | 117 | 42 | 75 | 31 | 5 | 0.2443 |
| Balance 2016 Abad Garcia y Pons.pdf | 11.719 | 133 | 98 | 35 | 84 | 8 | 0.1362 |
| Balance 2016 Asturias Ltda .pdf | 10.343 | 101 | 63 | 38 | 52 | 7 | 0.1687 |
| Balance 2016 Campomanes S A .pdf | 7.244 | 64 | 35 | 29 | 25 | 7 | 0.2659 |
| Balance 2017 - Igesur.pdf | 0.57 | 37 | 26 | 11 | 22 | 3 | 0.1477 |
| Balance 2017 - Naviera Orca.pdf | 0.81 | 62 | 23 | 39 | 22 | 0 | 0.04 |
| Balance Agricola El Comino dic 2018.pdf | 13.228 | 92 | 44 | 48 | 35 | 6 | 0.1898 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | 16.167 | 186 | 111 | 75 | 94 | 13 | 0.1449 |
| Balance Agricola Santa Amelia dic 2018.pdf | 14.668 | 96 | 36 | 60 | 31 | 2 | 0.1327 |
| Balance Capiro 2017-2018.pdf | 14.998 | 120 | 74 | 46 | 73 | 0 | 0.0108 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | 6.348 | 56 | 21 | 35 | 17 | 2 | 0.1782 |
| Balance Exportadora Agua Santa dic 2018.pdf | 13.578 | 78 | 32 | 46 | 24 | 4 | 0.2412 |
| Balance General SA JAHUEL 2020 V3.pdf | 1.745 | 214 | 126 | 88 | 85 | 8 | 0.3125 |
| Balance Vecchiola Dic_2016.pdf | 6.382 | 39 | 25 | 14 | 23 | 2 | 0.0725 |
| Balance Xpovin.pdf | 1.692 | 400 | 14 | 386 | 14 | 0 | 0.0 |
| EEFF - 2018 Los Nogales.pdf | 0.685 | 54 | 24 | 30 | 21 | 1 | 0.1148 |
| balance general guayacan 2020.pdf | 2.039 | 203 | 113 | 90 | 76 | 6 | 0.3145 |

---

## Archivos con errores

Ningún archivo generó errores.

## Archivos con warnings

Ningún archivo generó warnings.

---

## Manifiesto del dataset

| Archivo | Tamaño (KB) |
|---------|------------|
| BALANCE CLASIFICADO AICSA 2019.pdf | 684.4 |
| BALANCE ORIGINAL 2014.pdf | 412.0 |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | 97.7 |
| Balance 2015 - Transp Libardon Ltda.pdf | 76.5 |
| Balance 2016 Abad Garcia y Pons.pdf | 682.6 |
| Balance 2016 Asturias Ltda .pdf | 578.7 |
| Balance 2016 Campomanes S A .pdf | 398.1 |
| Balance 2017 - Igesur.pdf | 23.4 |
| Balance 2017 - Naviera Orca.pdf | 55.4 |
| Balance Agricola El Comino dic 2018.pdf | 757.0 |
| Balance Agricola El Dain Ltda 2011 2012.pdf | 275.6 |
| Balance Agricola Santa Amelia dic 2018.pdf | 761.4 |
| Balance Capiro 2017-2018.pdf | 182.4 |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | 47.7 |
| Balance Exportadora Agua Santa dic 2018.pdf | 690.9 |
| Balance General SA JAHUEL 2020 V3.pdf | 55.6 |
| Balance Vecchiola Dic_2016.pdf | 134.6 |
| Balance Xpovin.pdf | 4745.5 |
| EEFF - 2018 Los Nogales.pdf | 428.5 |
| balance general guayacan 2020.pdf | 44.7 |

---

_Benchmark ejecutado con benchmark/benchmark_runner.py_