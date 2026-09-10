# INFORME A10: CIERRE DE CALIDAD ESTÁTICA Y PREPARACIÓN DEL CANDIDATO EXPERIMENTAL

**Fecha:** 2026-09-10
**Proyecto:** . (directorio raíz del proyecto)
**Rama:** codex/mejoras-pendientes-20260826
**HEAD:** 9bc7892ada367defbebbc3ea34a7aefacf8bf536
**Remoto:** https://github.com/joserossel-dot/homologacion-balances.git
**Entorno:** macOS / Python 3.14.5 (Poetry venv) / pytest 8.4.2 / fpdf2 2.8.2 / openpyxl 3.1.5 / pdfplumber 0.11.10

---

## 1. Ruta, Rama, HEAD y Remoto Iniciales

- **Ruta Operativa:** `.` (directorio de trabajo raíz)
- **Rama:** `codex/mejoras-pendientes-20260826`
- **HEAD:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
- **Remoto:** `origin https://github.com/joserossel-dot/homologacion-balances.git`

---

## 2. Estado Git Inicial y Final

### Estado Git Inicial (`git status --short --untracked-files=all`):
```text
 M .gitignore
 M docs/ROADMAP_PRODUCCION_ONPREMISE.md
 M poetry.lock
 M pyproject.toml
?? experiments/pilot_coverage/classification/benchmark_classifier_isolated.py
?? experiments/pilot_coverage/classification/benchmark_runner.py
?? experiments/pilot_coverage/formats/expected_ground_truth.py
?? experiments/pilot_coverage/formats/experimental_double_column.py
?? experiments/pilot_coverage/formats/generate_fixtures.py
?? experiments/pilot_coverage/formats/shadow_extractor.py
?? reports/pilot_coverage/CLASIFICACION_VERIFICADA.md
?? reports/pilot_coverage/FORMATOS_VERIFICADOS.md
?? reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md
?? tests/experiments/pilot_coverage/test_benchmark_isolated.py
?? tests/experiments/pilot_coverage/test_confidence_benchmark.py
?? tests/experiments/pilot_coverage/test_format_coverage.py
?? tests/experiments/pilot_coverage/test_review_exceptions.py
?? tests/experiments/pilot_coverage/test_shadow_mode.py
```

### Estado Git Final (`git status --short --untracked-files=all`):
```text
 M .gitignore
 M docs/ROADMAP_PRODUCCION_ONPREMISE.md
 M poetry.lock
 M pyproject.toml
?? experiments/pilot_coverage/classification/benchmark_classifier_isolated.py
?? experiments/pilot_coverage/classification/benchmark_runner.py
?? experiments/pilot_coverage/formats/expected_ground_truth.py
?? experiments/pilot_coverage/formats/experimental_double_column.py
?? experiments/pilot_coverage/formats/generate_fixtures.py
?? experiments/pilot_coverage/formats/shadow_extractor.py
?? reports/pilot_coverage/CLASIFICACION_VERIFICADA.md
?? reports/pilot_coverage/FORMATOS_VERIFICADOS.md
?? reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md
?? reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md
?? tests/experiments/pilot_coverage/test_benchmark_isolated.py
?? tests/experiments/pilot_coverage/test_confidence_benchmark.py
?? tests/experiments/pilot_coverage/test_format_coverage.py
?? tests/experiments/pilot_coverage/test_review_exceptions.py
?? tests/experiments/pilot_coverage/test_shadow_mode.py
```

---

## 3. Inventario de Archivos Existentes antes de A10

- **Archivos Modificados Versionados Preexistentes:**
  - `.gitignore` (reglas específicas de modo sombra)
  - `docs/ROADMAP_PRODUCCION_ONPREMISE.md` (preexistente, no tocado)
  - `poetry.lock` (dependencias dev bloqueadas)
  - `pyproject.toml` (declaración `fpdf2 = "2.8.2"`)
- **Módulos Experimentales Creados en A5-A8:**
  - `experiments/pilot_coverage/classification/benchmark_classifier_isolated.py`
  - `experiments/pilot_coverage/classification/benchmark_runner.py`
  - `experiments/pilot_coverage/formats/expected_ground_truth.py`
  - `experiments/pilot_coverage/formats/experimental_double_column.py`
  - `experiments/pilot_coverage/formats/generate_fixtures.py`
  - `experiments/pilot_coverage/formats/shadow_extractor.py`
- **Suites de Pruebas Creadas en A5-A8:**
  - `tests/experiments/pilot_coverage/test_benchmark_isolated.py`
  - `tests/experiments/pilot_coverage/test_confidence_benchmark.py`
  - `tests/experiments/pilot_coverage/test_format_coverage.py`
  - `tests/experiments/pilot_coverage/test_review_exceptions.py`
  - `tests/experiments/pilot_coverage/test_shadow_mode.py`
- **Informes Creados:**
  - `reports/pilot_coverage/FORMATOS_VERIFICADOS.md`
  - `reports/pilot_coverage/CLASIFICACION_VERIFICADA.md`
  - `reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md`

---

## 4. Archivos Modificados por A10

1. `experiments/pilot_coverage/classification/benchmark_classifier_isolated.py` (corrección F541, tipado de `c_monto`, `nombre`, `tipo`, definición de `casos_con_esperado`).
2. `experiments/pilot_coverage/classification/benchmark_runner.py` (eliminación de `os`, `categoria`, orden de imports).
3. `experiments/pilot_coverage/formats/expected_ground_truth.py` (eliminación de `Any` no utilizado).
4. `experiments/pilot_coverage/formats/experimental_double_column.py` (corrección E741 `l` -> `linea`).
5. `experiments/pilot_coverage/formats/generate_fixtures.py` (import `pathlib`, ignores tipados localizados para `fpdf` y `openpyxl`).
6. `experiments/pilot_coverage/formats/shadow_extractor.py` (eliminación `tempfile`/`Set`, corrección E741 `l` -> `linea`, tipado explícito `map_e1`/`map_e3`, tipado seguro de `cuentas_e1`, eliminación de f-string estático).
7. `tests/experiments/pilot_coverage/test_benchmark_isolated.py` (reorden de imports, eliminación `CASOS_BENCHMARK`, aserción de imports diferidos).
8. `tests/experiments/pilot_coverage/test_confidence_benchmark.py` (eliminación `json` y `pathlib`).
9. `tests/experiments/pilot_coverage/test_format_coverage.py` (eliminación de 12 imports no utilizados, validación de tipo en `match[0].monto`).
10. `tests/experiments/pilot_coverage/test_review_exceptions.py` (eliminación `os`, `_con_saldo_relevante`, `OrigenColumna`, type ignore en `pandas`).
11. `tests/experiments/pilot_coverage/test_shadow_mode.py` (reorden de imports, eliminación `json`, `tempfile`, `ejecutar_modo_sombra_lote`, anotación `Optional[Dict[str, float]]` en `_crear_fila`).
12. `reports/pilot_coverage/FORMATOS_VERIFICADOS.md` (actualización canónica con resultados de calidad estática y clon limpio).
13. `reports/pilot_coverage/CLASIFICACION_VERIFICADA.md` (banner histórico/complementario).
14. `reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md` (banner histórico con recomendación de exclusión).
15. `reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md` (nuevo informe consolidado A10).

---

## 5. Resultado Ruff Inicial y Final

- **Inicial:** 41 errores (F541, F401, E402, F841, E741) $ightarrow$ Código de salida 1.
- **Final:** `All checks passed!` $ightarrow$ **0 errores, Código de salida 0**.
  - Comando: `poetry run ruff check experiments/pilot_coverage tests/experiments/pilot_coverage`

---

## 6. Resultado Mypy Inicial y Final

- **Inicial:** 11 errores en 3 archivos (imports sin stubs, anotaciones ausentes en diccionarios, incompatibilidades de tipos) $ightarrow$ Código de salida 1.
- **Final:** `Success: no issues found in 11 source files` $ightarrow$ **0 errores, Código de salida 0**.
  - Comando: `poetry run mypy --explicit-package-bases experiments/pilot_coverage tests/experiments/pilot_coverage`

---

## 7. Resultado de Compileall

- Comando: `poetry run python -m compileall -q experiments/pilot_coverage tests/experiments/pilot_coverage`
- **Resultado:** **0 errores de compilación de bytecode, Código de salida 0**.

---

## 8. Resultado de `git diff --check`

- Comando: `git diff --check`
- **Resultado:** **0 espacios en blanco espurios, 0 conflictos, Código de salida 0**.

---

## 9. Cantidad Experimental Recolectada

- Comando: `poetry run python -m pytest --collect-only -q tests/experiments/pilot_coverage/`
- **Total pruebas recolectadas:** **78**.

---

## 10. Resultado Experimental Exacto

- Comando: `poetry run python -m pytest -q tests/experiments/pilot_coverage/`
- **Resultado:** **73 passed, 1 skipped, 4 xfailed, 0 failed, 0 xpass en 10.56s (Código de salida 0)**.

---

## 11. Cantidad Integral Recolectada

- Comando: `poetry run python scripts/pytest_collection_gate.py`
- **Total pruebas recolectadas:** **1.562**.

---

## 12. Resultado Integral Exacto

- Comando: `poetry run python -m pytest -q`
- **Resultado:** **1.539 passed, 19 skipped, 4 xfailed, 0 failed, 0 xpass en 105.67s (Código de salida 0)**.

---

## 13. Advertencias Observadas

- Durante la regresión integral se registraron 3 advertencias emitidas por pandas en una prueba preexistente (`tests/test_manual_revision.py::TestNewAccountCreation::test_cuenta_nueva_aparece_en_agrupacion`):
  `DeprecationWarning: Bitwise inversion ~ on bool is deprecated and will be removed in Python 3.16.`
- No constituyen errores funcionales ni fallos de regresión.

---

## 14. Revisión de Privacidad y Distinción de Cadenas Sintéticas

- **Aclaración Documental (A12):** Durante A12 se detectó que la prueba A11 conservaba identificadores históricos mediante concatenación y se excluía a sí misma del escaneo. A12 eliminó esas referencias y sustituyó el control por patrones genéricos que inspeccionan también el propio archivo de prueba. La comprobación versionable no pretende contener ni enumerar una lista de organizaciones privadas conocidas.
- **Datos Privados Reales en Código:** **Cero datos privados reales**.
- **Cadenas Sintéticas Controladas:** Se utilizan exclusivamente marcadores sintéticos explícitamente autorizados (`ENTIDAD_SINTETICA_001`, `usuario_prueba`, `empresa-inexistente.example`, `76.123.456-7`, etc.).
- Ninguna cadena sensible se expone en reportes, métricas o logs.

---

## 15. Estado Real de Reproducibilidad Limpia

- **Comprobación Realizada:** La reproducibilidad de la suite experimental fue comprobada en un árbol temporal limpio instalado desde `poetry.lock` fuera del repositorio (`/private/var/folders/.../clean_repro_check_*`), donde se ejecutaron las pruebas experimentales en aislamiento.
- **Resultado de la Suite Experimental:** **73 passed, 1 skipped, 4 xfailed (Código de salida 0)**.
- **Alcance de la Verificación:** La regresión integral (1.562 pruebas) fue comprobada en el worktree operativo, pero no fue repetida dentro del entorno temporal limpio.
- **Limpieza:** Directorio temporal eliminado con éxito tras la ejecución.

---

## 16. Los Cuatro Defectos Caracterizados (XFail Strict)

1. `test_caracterizacion_01_original_falla_en_paralelo_con_codigo`: El separador original `double_column.py` falla en balances paralelos con código (superado en la variante experimental E3).
2. `test_caracterizacion_04_comparativo_incluye_fila_encabezado`: `ParserPDF` en balance comparativo de 2 períodos captura la fila de encabezado como cuenta.
3. `test_caracterizacion_05_notas_cercanas_fusiona_numero_nota`: En PDF plano sin líneas vectoriales, el número de nota contigua se fusiona con la glosa o importe.
4. `test_caracterizacion_06_descripciones_multilinea_fragmentadas`: Descripciones multilínea en PDF plano se fragmentan en filas separadas.

---

## 17. Riesgos Residuales

1. **Formato XLS Antiguo:** Permanece sin soporte nativo (`skipped`).
2. **Desacoplamiento de E3:** La variante E3 no está integrada en `parser_universal.py`; su evaluación se limita al modo sombra experimental.
3. **Deuda Técnica de Poetry:** Advertencias menores de formato en `pyproject.toml` para metadatos deprecados en versiones futuras de Poetry.

---

## 18. Confirmación de Integridad de Código Productivo

- `parser_universal.py`, `app_validacion.py`, `pipeline/`, `persistence/`, `src/`, `deployment/`, `diccionario.json` y `catalogo_maestro.json` se mantuvieron **100% intactos**.

---

## 19. Confirmación de Restricciones Operativas

- **Staging (`git add`):** CERO (`0`) archivos agregados al índice.
- **Commit:** CERO (`0`) commits ejecutados.
- **Push:** CERO (`0`) operaciones de push.
- **Despliegue:** CERO (`0`) despliegues.
- **Neon / BD Remotas:** CERO (`0`) conexiones a Neon; CERO (`0`) migraciones.

---

## 20. Conclusión

$$\mathbf{APTO\ PARA\ PREPARAR\ SELECCI\acute{O}N\ GIT}$$
