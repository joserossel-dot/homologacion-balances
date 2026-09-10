# INFORME A11: CORRECCIÓN FINAL DE PRIVACIDAD Y PRECISIÓN DOCUMENTAL

**Fecha:** 2026-09-10
**Proyecto:** . (directorio raíz del proyecto)
**Rama:** `codex/mejoras-pendientes-20260826`
**HEAD:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
**Remoto:** `origin https://github.com/joserossel-dot/homologacion-balances.git`
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
?? reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md
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
?? reports/pilot_coverage/INFORME_A11_PRIVACIDAD_Y_REPRODUCIBILIDAD.md
?? reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md
?? tests/experiments/pilot_coverage/test_benchmark_isolated.py
?? tests/experiments/pilot_coverage/test_confidence_benchmark.py
?? tests/experiments/pilot_coverage/test_format_coverage.py
?? tests/experiments/pilot_coverage/test_review_exceptions.py
?? tests/experiments/pilot_coverage/test_shadow_mode.py
```

---

## 3. Inventario de Archivos Existentes antes de A11

- **Archivos Modificados Versionados Preexistentes:**
  - `.gitignore`
  - `docs/ROADMAP_PRODUCCION_ONPREMISE.md`
  - `poetry.lock`
  - `pyproject.toml`
- **Módulos y Tests Experimentales:**
  - `experiments/pilot_coverage/` (6 módulos Python)
  - `tests/experiments/pilot_coverage/` (5 módulos de prueba)
- **Informes Preexistentes:**
  - `reports/pilot_coverage/FORMATOS_VERIFICADOS.md`
  - `reports/pilot_coverage/CLASIFICACION_VERIFICADA.md`
  - `reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md`
  - `reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md`

---

## 4. Archivos Modificados por A11

1. `tests/experiments/pilot_coverage/test_shadow_mode.py`: Sustitución de nombres y rutas potencialmente identificables por cadenas estrictamente sintéticas (`ENTIDAD_SINTETICA_001`, `usuario_prueba`, `empresa-inexistente.example`).
2. `reports/pilot_coverage/FORMATOS_VERIFICADOS.md`: Aclaración exacta de reproducibilidad (suite experimental en entorno temporal limpio vs. suite general en worktree operativo).
3. `reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md`: Aclaración exacta de reproducibilidad en sección 15.
4. `reports/pilot_coverage/INFORME_A11_PRIVACIDAD_Y_REPRODUCIBILIDAD.md`: Nuevo informe consolidado A11.

---

## 5. Búsquedas de Privacidad y Alcance

- **Aclaración Documental (A12):** Durante A12 se detectó que la prueba A11 conservaba identificadores históricos mediante concatenación y se excluía a sí misma del escaneo. A12 eliminó esas referencias y sustituyó el control por patrones genéricos que inspeccionan también el propio archivo de prueba. La comprobación versionable no pretende contener ni enumerar una lista de organizaciones privadas conocidas.
- Todas las cadenas presentes en el código de pruebas y reportes fueron sustituidas por marcadores puramente sintéticos (`ENTIDAD_SINTETICA_001`, `usuario_prueba`, `empresa-inexistente.example`, `76.123.456-7`).

---

## 6. Reemplazos de Privacidad Aplicados en `test_shadow_mode.py`

| Identificador Previo | Reemplazo Sintético | Motivo |
| :--- | :--- | :--- |
| Nombres con entidades históricas y RUT | `ENTIDAD_SINTETICA_001 76.123.456-7` | Evitar coincidencia con empresas o clientes |
| Archivos PDF con nombres de empresas | `balance_empresa_ficticia_001.pdf` | Evitar coincidencia con empresa real |
| Rutas absolutas macOS / POSIX | `/ruta_sintetica/usuario_prueba/data/balance_confidencial.pdf` | Sanitización de usuario y ruta |
| Rutas absolutas Windows con carpetas empresariales | `C:\Contabilidad\ENTIDAD_SINTETICA_001\balance.pdf` | Sanitización de ruta Windows |
| Rutas absolutas Linux (`/home/...`) | `/home/usuario_prueba/privado.pdf` | Sanitización de usuario Linux |
| Correos con dominios corporativos | `contacto@empresa-inexistente.example` | Uso de TLD de prueba `.example` según RFC 2606 |
| Identificadores de error en tests | `ENTIDAD_SINTETICA_002` | Nomenclatura sintética estandarizada |
| Archivos de balance en excepciones | `Doc Balance_ENTIDAD_SINTETICA_001_76.123.456-7_2023.pdf` | Entidad genérica sintética |

---

## 7. Matriz de Clasificación de Privacidad

| Categoría | Estado en Código/Reportes | Mecanismo de Protección |
| :--- | :--- | :--- |
| **Rutas de Usuario (POSIX/macOS/Linux)** | Redactadas (`[REDACTED_PATH]`) | Función `sanitizar_mensaje_privacidad` con regex multiplataforma |
| **Rutas Windows (`C:\...`)** | Redactadas (`[REDACTED_PATH]`) | Regex Windows con barras invertidas soportadas |
| **Nombres de Archivos (`.pdf`, `.xlsx`)** | Redactados (`[REDACTED_FILE]`) | Regex de extensiones de archivo |
| **RUTs / Cédulas** | Redactados (`[REDACTED_RUT]`) | Regex de formato chileno $XX.XXX.XXX-X$ |
| **Identificadores en Manifiesto** | Aceptados solo si cumplen whitelist técnica | Expresión regular `^SHADOW-DOC-(?:[0-9]{2}-)?[a-f0-9]{12}$` |
| **Nombres en Tests Unitarios** | 100% sintéticos (`ENTIDAD_SINTETICA_*`) | Valores de prueba controlados sin datos de producción |

---

## 8. Aclaración Documental sobre Reproducibilidad

Se precisó en toda la documentación la siguiente distinción técnica:
> *"La reproducibilidad de la suite experimental fue comprobada en un árbol temporal limpio instalado desde `poetry.lock`. La regresión integral fue comprobada en el worktree operativo, pero no fue repetida dentro del entorno temporal limpio."*

---

## 9. Calidad Estática: Ruff

- **Comando:** `poetry run ruff check experiments/pilot_coverage tests/experiments/pilot_coverage`
- **Resultado:** `All checks passed!` (**0 errores, Código 0**).

---

## 10. Calidad Estática: Mypy

- **Comando:** `poetry run mypy --explicit-package-bases experiments/pilot_coverage tests/experiments/pilot_coverage`
- **Resultado:** `Success: no issues found in 11 source files` (**0 errores, Código 0**).

---

## 11. Compilación Bytecode: Compileall

- **Comando:** `poetry run python -m compileall -q experiments/pilot_coverage tests/experiments/pilot_coverage`
- **Resultado:** **0 errores de sintaxis o bytecode (Código 0)**.

---

## 12. Integridad de Formato: `git diff --check`

- **Comando:** `git diff --check`
- **Resultado:** **0 espacios espurios, 0 conflictos (Código 0)**.

---

## 13. Verificación de `test_shadow_mode.py`

- **Comando:** `poetry run python -m pytest -q tests/experiments/pilot_coverage/test_shadow_mode.py`
- **Resultado:** **24 passed in 3.65s (Código 0)**.

---

## 14. Verificación de Suite Experimental Completa

- **Comando:** `poetry run python -m pytest -q tests/experiments/pilot_coverage/`
- **Resultado:** **73 passed, 1 skipped, 4 xfailed in 10.42s (Código 0)**.

---

## 15. Confirmación de Restricciones Operativas

- **Código Productivo:** `parser_universal.py`, `app_validacion.py`, `pipeline/`, etc. permanecen **100% intactos**.
- **Bases de Datos / Neon:** CERO (`0`) conexiones a Neon, migraciones o alteraciones de datos persistentes.
- **Diccionarios:** `diccionario.json` y `catalogo_maestro.json` **100% intactos**.
- **Staging (`git add`):** CERO (`0`) archivos agregados al índice (`git diff --cached --name-status` vacío).
- **Commit / Push / Despliegue:** CERO (`0`) commits, CERO (`0`) push, CERO (`0`) despliegues.

---

## 16. Conclusión y Veredicto

$$\mathbf{APTO\ PARA\ PREPARAR\ SELECCI\acute{O}N\ GIT}$$
