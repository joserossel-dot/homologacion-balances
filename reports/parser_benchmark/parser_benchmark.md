# Benchmark: Parser v1 vs Parser Core 2.0

**Fecha:** 2026-07-09 20:00

**Documentos:** 20 PDFs del Holdout


---

## Resumen global

| Métrica | Valor |
|---------|-------|
| Tiempo total v1 | 173.8s |
| Tiempo total v2 | 176.5s |
| Promedio v1 | 8.688s |
| Promedio v2 | 8.825s |
| Speedup medio | 0.98x |
| Total cuentas v1 | 2692 |
| Total cuentas v2 | 2692 |
| Cuentas compartidas | 2692 (100.0%) |
| Solo en v1 | 0 |
| Solo en v2 | 0 |
| Docs con match exacto | 20/20 (100.0%) |
| Confianza layout promedio | 0.79 |

## Distribución de layouts detectados (v2)

| Layout | Documentos |
|--------|------------|
| activo, perdida | 2 |
| activo, pasivo, codigo, ganancia | 2 |
| activo, pasivo, perdida, ganancia | 2 |
| perdida, activo | 2 |
| resultado, activo, pasivo, perdida, ganancia, codigo, nombre | 1 |
| activo, pasivo, codigo, ganancia, perdida, patrimonio | 1 |
| activo, pasivo, codigo, nombre, ganancia, patrimonio, perdida | 1 |
| activo, pasivo, ganancia | 1 |
| activo, pasivo, codigo, patrimonio, resultado, ganancia, perdida | 1 |
| resultado, nombre, codigo, activo, pasivo, perdida, ganancia | 1 |
| resultado, perdida, patrimonio | 1 |
| nombre, activo, pasivo, ganancia, patrimonio, resultado, perdida | 1 |
| activo, pasivo, perdida, ganancia, codigo, nombre, saldo, resultado | 1 |
| activo, pasivo, perdida, ganancia, patrimonio, resultado | 1 |
| activo, perdida, pasivo | 1 |
| activo, pasivo, perdida, ganancia, codigo, nombre, saldo | 1 |

## Columnas asignadas (v2)

| Columna | Cuentas |
|---------|---------|
| desconocido | 1399 |
| ganancia | 693 |
| activo | 219 |
| perdida | 204 |
| pasivo | 177 |

## Resultados por documento

| Documento | v1 cuentas | v2 cuentas | Match | v1 seg | v2 seg | Speedup | Layout | Conf |
|-----------|-----------|-----------|-------|--------|--------|---------|--------|------|
| BALANCE CLASIFICADO AICSA 2019.pdf | 101 | 101 | ✓ | 0.61 | 0.60 | 1.02x | activo, perdida | 60% |
| BALANCE ORIGINAL 2014.pdf | 371 | 371 | ✓ | 27.74 | 26.81 | 1.03x | resultado, activo, p | 100% |
| Balance 2015 - Soc Com e Inv Campoamor SA.pdf | 168 | 168 | ✓ | 13.82 | 13.99 | 0.99x | activo, pasivo, codi | 83% |
| Balance 2015 - Transp Libardon Ltda.pdf | 117 | 117 | ✓ | 11.70 | 15.13 | 0.77x | activo, pasivo, codi | 100% |
| Balance 2016 Abad Garcia y Pons.pdf | 133 | 133 | ✓ | 12.11 | 11.15 | 1.09x | activo, pasivo, codi | 83% |
| Balance 2016 Asturias Ltda .pdf | 101 | 101 | ✓ | 10.08 | 10.20 | 0.99x | activo, pasivo, codi | 100% |
| Balance 2016 Campomanes S A .pdf | 64 | 64 | ✓ | 7.24 | 7.34 | 0.99x | activo, pasivo, gana | 75% |
| Balance 2017 - Igesur.pdf | 37 | 37 | ✓ | 0.23 | 0.10 | 2.26x | activo, pasivo, codi | 100% |
| Balance 2017 - Naviera Orca.pdf | 62 | 62 | ✓ | 0.35 | 0.35 | 0.98x | activo, pasivo, perd | 30% |
| Balance Agricola El Comino dic 2018.pdf | 92 | 92 | ✓ | 14.47 | 14.31 | 1.01x | perdida, activo | 60% |
| Balance Agricola El Dain Ltda 2011 2012.pdf | 186 | 186 | ✓ | 15.77 | 15.93 | 0.99x | resultado, nombre, c | 100% |
| Balance Agricola Santa Amelia dic 2018.pdf | 96 | 96 | ✓ | 14.68 | 14.77 | 0.99x | activo, perdida | 60% |
| Balance Capiro 2017-2018.pdf | 120 | 120 | ✓ | 14.66 | 15.22 | 0.96x | resultado, perdida,  | 61% |
| Balance Clasificado y Estado resultado 2017 Inversiones San Marcelo Ltda.pdf | 56 | 56 | ✓ | 6.68 | 6.88 | 0.97x | nombre, activo, pasi | 100% |
| Balance Exportadora Agua Santa dic 2018.pdf | 78 | 78 | ✓ | 13.75 | 14.27 | 0.96x | perdida, activo | 60% |
| Balance General SA JAHUEL 2020 V3.pdf | 214 | 214 | ✓ | 0.80 | 1.06 | 0.75x | activo, pasivo, perd | 100% |
| Balance Vecchiola Dic_2016.pdf | 39 | 39 | ✓ | 6.85 | 5.91 | 1.16x | activo, pasivo, perd | 100% |
| Balance Xpovin.pdf | 400 | 400 | ✓ | 1.02 | 1.16 | 0.88x | activo, pasivo, perd | 30% |
| EEFF - 2018 Los Nogales.pdf | 54 | 54 | ✓ | 0.16 | 0.16 | 1.00x | activo, perdida, pas | 75% |
| balance general guayacan 2020.pdf | 203 | 203 | ✓ | 1.03 | 1.16 | 0.89x | activo, pasivo, perd | 100% |

---

*Generado por `scripts/run_parser_benchmark.py`*
*Parser v1 = parser_universal.ParserPDF | Parser v2 = parsers.ParserCore2*
*No se modificó parser_universal.py. No se afectó producción.*