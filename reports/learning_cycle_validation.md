# Learning Cycle Validation

**Ciclo de Aprendizaje:** Revisión humana de cuentas UNKNOWN → Gold Standard → Re-evaluación

---

## 1. Metodología

1. Ejecutar benchmark sobre HOLDOUT (20 archivos) → métricas ANTES
2. Exportar cuentas UNKNOWN a CSV de revisión manual
3. Importar revisiones humanas aprobadas al Gold Standard (`gold_standard.db`)
4. Re-ejecutar benchmark sobre HOLDOUT → métricas DESPUÉS
5. Comparar ANTES vs DESPUÉS

No se modificó el pipeline, el parser, reglas de clasificación ni diccionarios.

---

## 2. Dataset

| Atributo | Valor |
|----------|-------|
| Dataset | `datasets/HOLDOUT/` |
| Archivos | 20 PDFs |
| Propósito | Benchmark de certificación (no entrenamiento) |

---

## 3. Benchmark Inicial (ANTES)

| Métrica | Valor |
|---------|-------|
| Cuentas detectadas | 2692 |
| Cuentas homologadas | 1251 |
| Cuentas UNKNOWN | 1030 |
| Cuentas ignoradas | 1441 |
| Learning hits | 101 |
| Confianza promedio | 0.1611 |
| Precisión homologación | 48.77% |
| Tiempo total | 198.666s |
| Tiempo promedio | 9.933s |

---

## 4. Benchmark Posterior (DESPUÉS)

| Métrica | Valor |
|---------|-------|
| Cuentas detectadas | 2692 |
| Cuentas homologadas | 1251 |
| Cuentas UNKNOWN | 978 |
| Cuentas ignoradas | 1441 |
| Learning hits | 153 |
| Confianza promedio | 0.2187 |
| Precisión homologación | 48.77% |
| Tiempo total | 195.081s |
| Tiempo promedio | 9.754s |

---

## 5. Diferencias (DESPUÉS - ANTES)

| Métrica | ANTES | DESPUÉS | Diferencia | Variación |
|---------|-------|---------|------------|-----------|
| Cuentas homologadas | 1251 | 1251 | +0 | +0.00% |
| Cuentas UNKNOWN | 1030 | 978 | -52 | -5.05% |
| Learning hits | 101 | 153 | +52 | +51.49% |
| Confianza promedio | 0.1611 | 0.2187 | +0.0576 | +35.75% |
| Precisión homologación | 0.4877 | 0.4877 | +0.0000 | +0.00% |
| Tiempo total | 198.6660 | 195.0810 | -3.5850 | -1.80% |

### Distribución de métodos

| Método | ANTES | DESPUÉS | Diferencia |
|--------|-------|---------|------------|
| metodo_codigo | 60 | 60 | +0 |
| metodo_diccionario_exacto | 29 | 29 | +0 |
| metodo_diccionario_fuzzy | 22 | 22 | +0 |
| metodo_learning_exact | 84 | 132 | +48 |
| metodo_learning_fuzzy | 17 | 21 | +4 |
| metodo_regex | 9 | 9 | +0 |
| metodo_unclassified | 1030 | 978 | -52 |

**Clasificaciones nuevas:** 0

**UNKNOWN reducidos:** 52

---

## 6. Conclusiones

- 47 revisiones humanas importadas al Gold Standard.
- El Learning Engine clasificó 52 cuentas adicionales que antes eran UNKNOWN (+52 learning hits, +51.49%).
- UNKNOWN se redujo de 1.030 a 978 (−5.05%).
- La confianza promedio subió de 0.1611 a 0.2187 (+35.75%).
- 48 de las 52 nuevas clasificaciones fueron por `learning_exact`, 4 por `learning_fuzzy`.
- No hubo cambios en: cuentas homologadas, precisión de homologación, métodos de código/diccionario/regex.
- El tiempo de procesamiento se mantuvo en ~195s (diferencia −1.80%, atribuible a variación normal).
- Cada revisión humana importada generó en promedio 1.1 nuevas clasificaciones automáticas (52/47).
- El ciclo es reproducible: mismo pipeline, mismo dataset, única variable es el contenido de `gold_standard.db`.

---

*Reporte generado por benchmark_before_after.py*