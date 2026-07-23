# Stress Test: Parser v1 vs Parser Core 2.0

**Fecha:** 2026-07-09 21:20

**Documentos analizados:** 206


---

## Resumen global

| Métrica | Valor |
|---------|-------|
| Total documentos | 206 |
| Tiempo total v1 | 1550.2s |
| Tiempo total v2 | 1557.0s |
| Cuentas v1 | 30829 |
| Cuentas v2 | 30829 |
| Resultados idénticos (TIE) | 206/206 (100.0%) |
| Documentos con diferencias | 0 |

## Veredictos

| Veredicto | Cantidad |
|-----------|----------|
| TIE | 206 |

## Top 20 casos más difíciles (DocumentAssessment)

| Archivo | Grupo | PC | LC | CR | v1 | v2 | Verdict |
|---------|-------|----|----|----|----|----|---------|
| Balance 2019 FIRMADO.pdf | edge_cases | 0.00 | 0.10 | 1.00 | 0 | 0 | TIE |
| Balance General Año 2016 firmado.pdf | edge_cases | 0.00 | 0.10 | 1.00 | 0 | 0 | TIE |
| Balance Xpovin.pdf | HOLDOUT | 0.00 | 0.20 | 0.60 | 400 | 400 | TIE |
| Balance Xpovin.pdf | edge_cases | 0.00 | 0.20 | 0.60 | 400 | 400 | TIE |
| balance cm 2016.pdf | validacion | 0.00 | 0.60 | 0.65 | 120 | 120 | TIE |
| balance cm 2015.pdf | validacion | 0.00 | 0.60 | 0.62 | 166 | 166 | TIE |
| balance cm 2017.pdf | validacion | 0.00 | 0.60 | 0.55 | 232 | 232 | TIE |
| Balance Chillan.xlsx | edge_cases | 0.00 | 0.50 | 0.44 | 0 | 0 | TIE |
| Resumen Balance san Osvaldo 2018.xlsx | edge_cases | 0.00 | 0.50 | 0.36 | 0 | 0 | TIE |
| Balances tuniche explicacionxlsx.xlsx | edge_cases | 0.00 | 0.50 | 0.34 | 0 | 0 | TIE |
| Balance Agrícola González Ltda.pdf | validacion | 0.00 | 0.60 | 0.41 | 600 | 600 | TIE |
| Balance Agrícola González Ltda_150.pdf | validacion | 0.00 | 0.60 | 0.41 | 600 | 600 | TIE |
| Balance Agrícola González Ltda_153.pdf | validacion | 0.00 | 0.60 | 0.41 | 600 | 600 | TIE |
| Balance Viña Folatre.pdf | validacion | 0.00 | 0.60 | 0.41 | 609 | 609 | TIE |
| Balance Viña Folatre_146.pdf | validacion | 0.00 | 0.60 | 0.41 | 609 | 609 | TIE |
| Balance Viña Folatre_148.pdf | validacion | 0.00 | 0.60 | 0.41 | 609 | 609 | TIE |
| Balance Exportadora Gonzagri.pdf | validacion | 0.00 | 0.60 | 0.41 | 631 | 631 | TIE |
| Balance Exportadora Gonzagri_155.pdf | validacion | 0.00 | 0.60 | 0.41 | 631 | 631 | TIE |
| Balance Exportadora Gonzagri_157.pdf | validacion | 0.00 | 0.60 | 0.41 | 631 | 631 | TIE |
| EEFF - Histórico (2).xlsx | edge_cases | 0.00 | 0.50 | 0.33 | 0 | 0 | TIE |

## Conclusión

**NO se encontraron diferencias entre Parser v1 y Parser Core 2.0.**

En los 206 documentos analizados, ambos parsers produjeron resultados idénticos en número de cuentas, nombres, códigos, montos y asignación de columnas.

Parser Core 2.0 NO es superior en capacidad de parseo. Su valor está en la arquitectura modular, las métricas (ParseMetrics, LayoutDetector), la configuración externalizada y la preparación para OCR pluggable — pero el output de parseo es el mismo porque v2 envuelve las mismas funciones de extracción.

### ¿Qué falta para que v2 sea superior?

1. **LayoutDetector integrado** — hoy es informativo; debe modificar la asignación de columnas
2. **Mejor OCR** — interfaz preparada pero sin implementación alternativa real
3. **Parseo paralelo** — estructura lista pero sin threading
4. **Caché de OCR** — config listo pero sin implementación
5. **Validación post-parseo** — usar ParseMetrics para rechazar/alertar

---

*Generado por `scripts/run_parser_stress_test.py`*
*Parser v1 = parser_universal.ParserPDF | Parser v2 = parsers.ParserCore2*
*No se modificó parser_universal.py. No se afectó producción.*
*No se escribieron nuevas funcionalidades. No se optimizó.*