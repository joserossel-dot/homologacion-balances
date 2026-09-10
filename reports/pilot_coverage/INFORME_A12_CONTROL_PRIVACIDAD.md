# INFORME A12: ELIMINACIÓN REAL DE IDENTIFICADORES PRIVADOS Y CORRECCIÓN DEL CONTROL DE PRIVACIDAD

**Fecha:** 2026-09-10
**Proyecto:** . (directorio raíz del proyecto)
**Rama:** `codex/mejoras-pendientes-20260826`
**HEAD:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
**Remoto:** `origin https://github.com/joserossel-dot/homologacion-balances.git`
**Entorno:** macOS / Python 3.14.5 (Poetry venv) / pytest 8.4.2 / fpdf2 2.8.2 / openpyxl 3.1.5 / pdfplumber 0.11.10

---

## 1. Ruta, Rama, HEAD y Remoto

- **Ruta del Proyecto:** `.` (directorio de trabajo raíz del repositorio)
- **Rama Verificada:** `codex/mejoras-pendientes-20260826`
- **HEAD Verificado:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
- **Remoto Verificado:** `origin https://github.com/joserossel-dot/homologacion-balances.git`

---

## 2. Estado Git Inicial

Al iniciar el Encargo A12, el estado de trabajo coincidía exactamente con el inventario esperado:
```text
## codex/mejoras-pendientes-20260826...origin/codex/mejoras-pendientes-20260826
 M .gitignore
 M docs/ROADMAP_PRODUCCION_ONPREMISE.md
 M poetry.lock
 M pyproject.toml
?? experiments/
?? reports/
?? tests/experiments/
```
El índice de staging se encontraba 100% vacío (`git diff --cached` con 0 archivos).

---

## 3. Descripción del Defecto Detectado tras A11

Durante la revisión independiente posterior al Encargo A11, se identificaron dos defectos en `tests/experiments/pilot_coverage/test_shadow_mode.py`:
1. **Identificadores Históricos Ocultos:** La lista de patrones de prueba contenía tres nombres reconstruidos mediante concatenación de cadenas (`IDENTIFICADOR_PRIVADO_1`, `IDENTIFICADOR_PRIVADO_2`, `IDENTIFICADOR_PRIVADO_3`), lo que conservaba referencias ofuscadas en el código versionable.
2. **Autoexclusión de la Prueba:** El escáner de privacidad contenía la instrucción `if file_path.name == "test_shadow_mode.py": continue`, excluyendo deliberadamente a la propia prueba de la inspección.

---

## 4. Confirmación de Eliminación de IDENTIFICADOR_PRIVADO_1, 2 y 3

Se eliminaron completamente las tres expresiones que reconstruían nombres reales en `tests/experiments/pilot_coverage/test_shadow_mode.py`. No fueron sustituidas por variables separadas, Base64, hashes, inversión, abreviaturas ni ninguna otra forma de ofuscación. La suite versionable no contiene ni intenta almacenar una lista fija de organizaciones privadas.

---

## 5. Confirmación de Eliminación de la Autoexclusión

Se eliminó la condición `if file_path.name == "test_shadow_mode.py": continue`. El escáner de privacidad ahora inspecciona el 100% de los archivos de texto versionables, incluido `tests/experiments/pilot_coverage/test_shadow_mode.py`.

---

## 6. Diseño del Nuevo Control Genérico de Privacidad

La función `_escanear_violaciones_privacidad_texto` y la prueba `test_privacidad_sin_rutas_ni_nombres_privados_en_codigo` fueron rediseñadas para verificar reglas estructurales genéricas:

1. **Rutas Personales no Sintéticas:** Expresiones regulares que detectan directorios de usuario en macOS (`/Users/<user>`), Linux (`/home/<user>`) y Windows (`[A-Z]:\Users\<user>`), permitiendo únicamente el marcador explícito `/Users/usuario_prueba` o rutas relativas del proyecto.
2. **Enlaces `file://` Locales:** Detección de URIs locales no sintéticas.
3. **Correos Electrónicos:** Validación de que todo correo utilice exclusivamente dominios reservados para pruebas según RFC 2606 (`.example`, `.invalid`, `.test`, `.localhost`, `@example.com`, `@example.org`, `@example.net`) o el fixture de aislamiento `@neon.tech`.
4. **Credenciales de Base de Datos:** Detección de cadenas de conexión PostgreSQL que contengan usuarios o contraseñas fuera de los marcadores sintéticos autorizados (`test_user`, `test_pass`, `neon_user`, `neon_pass`, `blocked_user`, `postgres`).
5. **RUTs no Autorizados:** Verificación de que ningún identificador fiscal con formato chileno figure en el código, excepto el fixture sintético explícito `76.123.456-7`.
6. **Secretos y Tokens:** Detección de patrones conocidos de tokens (`sk_live_`, `ghp_`, `AKIA`).
7. **Marcadores de Volcados Productivos:** Detección de encabezados de volcado (`pg_dump`, `COPY ... FROM stdin`).
8. **Prueba de Detección Positiva:** Se añadió `test_detector_privacidad_detecta_fugas_simuladas_en_memoria` para demostrar que el detector identifica positivamente cualquier fuga simulada en memoria.
9. **Soporte Local Opcional:** Soporte para leer patrones privados adicionales desde `reports/pilot_coverage/local/privacy_patterns.local.txt` (ignorado por `.gitignore`) si existiera en entornos privados locales, sin fallar si el archivo no existe.

---

## 7. Directorios y Extensiones Inspeccionados

El escaneo de privacidad recorre:
- `experiments/pilot_coverage/`
- `tests/experiments/pilot_coverage/`
- `reports/pilot_coverage/`

Extensiones inspeccionadas: `.py`, `.md`, `.json`.

---

## 8. Exclusiones Técnicas Legítimas

Las únicas exclusiones aplicadas son:
- Directorios de caché bytecode (`__pycache__`).
- Archivos binarios de assets (`.png`, `.pdf`, `.xlsx`, `.pyc`).
- Resultados de ejecución local ignorados por Git (`reports/pilot_coverage/local/**`).

---

## 9. Cadenas Sintéticas Permitidas (Whitelist)

- `ENTIDAD_SINTETICA_001`, `ENTIDAD_SINTETICA_002`
- `usuario_prueba`
- `empresa-inexistente.example`
- `test_user`, `test_pass`, `neon_user`, `neon_pass`, `blocked_user`
- `SHADOW-DOC-001`, `SHADOW-DOC-01-ac0b61687dea`, `SHADOW-DOC-02-NOTFOUND`, `SHADOW-DOC-NOTFOUND`
- `76.123.456-7`
- `balance_empresa_ficticia_001.pdf`
- `[REDACTED_PATH]`, `[REDACTED_FILE]`, `[REDACTED_RUT]`, `[REDACTED_MAIL]`

---

## 10. Resultados de Validación y Calidad Estática

1. **Ruff Linter:**
   - Comando: `poetry run ruff check experiments/pilot_coverage tests/experiments/pilot_coverage`
   - **Resultado:** `All checks passed!` (**0 errores, Código 0**).
2. **Mypy Type Checker:**
   - Comando: `poetry run mypy --explicit-package-bases experiments/pilot_coverage tests/experiments/pilot_coverage`
   - **Resultado:** `Success: no issues found in 11 source files` (**0 errores, Código 0**).
3. **Compileall:**
   - Comando: `poetry run python -m compileall -q experiments/pilot_coverage tests/experiments/pilot_coverage`
   - **Resultado:** **0 errores de compilación de bytecode (Código 0)**.
4. **Git Diff Check:**
   - Comando: `git diff --check`
   - **Resultado:** **0 espacios espurios / 0 conflictos (Código 0)**.
5. **Prueba de Modo Sombra y Privacidad:**
   - Comando: `poetry run python -m pytest -q tests/experiments/pilot_coverage/test_shadow_mode.py`
   - **Resultado:** **25 passed in 2.98s (Código 0)**. (25 pruebas aprobadas: 24 previas + 1 nueva prueba de validación de detector en memoria).
6. **Suite Experimental Completa:**
   - Comando: `poetry run python -m pytest -q tests/experiments/pilot_coverage/`
   - **Resultado:** **74 passed, 1 skipped, 4 xfailed in 9.38s (Código 0)**.

---

## 11. Escaneo Manual Complementario

| Categoría de Coincidencia | Cantidad | Observación |
| :--- | :---: | :--- |
| **Datos privados reales** | **0** | Certificado mediante escaneo estático y manual. |
| **Identificadores históricos ofuscados** | **0** | Eliminados totalmente (IDENTIFICADOR_PRIVADO_1, 2 y 3). |
| **Cadenas sintéticas controladas** | **28** | Fixtures unitarios autorizados (`ENTIDAD_SINTETICA_*`, `usuario_prueba`, `76.123.456-7`). |
| **Patrones técnicos / Regex** | **14** | Definiciones de expresiones regulares de validación de formato. |

---

## 12. Estado Git Final e Inventario

### Estado de Ramas (`git status --short --branch`):
```text
## codex/mejoras-pendientes-20260826...origin/codex/mejoras-pendientes-20260826
 M .gitignore
 M docs/ROADMAP_PRODUCCION_ONPREMISE.md
 M poetry.lock
 M pyproject.toml
?? experiments/
?? reports/
?? tests/experiments/
```

### Detalle de Archivos no Rastreados (`git status --short --untracked-files=all`):
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
?? reports/pilot_coverage/INFORME_A12_CONTROL_PRIVACIDAD.md
?? reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md
?? tests/experiments/pilot_coverage/test_benchmark_isolated.py
?? tests/experiments/pilot_coverage/test_confidence_benchmark.py
?? tests/experiments/pilot_coverage/test_format_coverage.py
?? tests/experiments/pilot_coverage/test_review_exceptions.py
?? tests/experiments/pilot_coverage/test_shadow_mode.py
```

### Comprobación del Índice Staging:
- Comando: `git diff --cached --name-status`
- **Resultado:** **Vacío (`0` archivos en stage)**.

---

## 13. Riesgos Residuales

1. **Formato XLS Antiguo:** Permanece sin soporte nativo (`skipped`), documentado de manera explícita.
2. **Aislamiento de E3:** La variante E3 no reemplaza el código productivo `parser_universal.py`, limitándose al modo sombra experimental.
3. **Dependencia de Archivos Locales:** El soporte de patrones privados locales depende de la existencia opcional de archivos ignorados fuera de Git.

---

## 14. Selección Git Propuesta para Revisión de Codex

Los siguientes archivos están listos para preparación de commit por parte del operador/Codex:
```text
.gitignore
pyproject.toml
poetry.lock
experiments/pilot_coverage/classification/benchmark_classifier_isolated.py
experiments/pilot_coverage/classification/benchmark_runner.py
experiments/pilot_coverage/formats/expected_ground_truth.py
experiments/pilot_coverage/formats/experimental_double_column.py
experiments/pilot_coverage/formats/generate_fixtures.py
experiments/pilot_coverage/formats/shadow_extractor.py
tests/experiments/pilot_coverage/test_benchmark_isolated.py
tests/experiments/pilot_coverage/test_confidence_benchmark.py
tests/experiments/pilot_coverage/test_format_coverage.py
tests/experiments/pilot_coverage/test_review_exceptions.py
tests/experiments/pilot_coverage/test_shadow_mode.py
reports/pilot_coverage/FORMATOS_VERIFICADOS.md
reports/pilot_coverage/CLASIFICACION_VERIFICADA.md
reports/pilot_coverage/INFORME_A10_CALIDAD_ESTATICA.md
reports/pilot_coverage/INFORME_A11_PRIVACIDAD_Y_REPRODUCIBILIDAD.md
reports/pilot_coverage/INFORME_A12_CONTROL_PRIVACIDAD.md
```

### Archivos Excluidos Expresamente:
- `docs/ROADMAP_PRODUCCION_ONPREMISE.md` (modificación preexistente fuera de alcance)
- `reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md` (informe histórico anterior desaconsejado)

---

## 15. Confirmación de Restricciones Operativas

- **Código Productivo:** `parser_universal.py`, `app_validacion.py`, `pipeline/`, etc. **100% intactos**.
- **Bases de Datos / Neon:** CERO (`0`) conexiones a Neon, migraciones o modificaciones de esquemas.
- **Diccionarios:** `diccionario.json` y `catalogo_maestro.json` **100% intactos**.
- **Staging / Commits / Pushes / Deploys:** CERO (`0`) ejecuciones de `git add`, `git commit`, `git push` ni despliegues en Render.

---

## 16. Conclusión y Veredicto

$$\mathbf{APTO\ PARA\ PREPARAR\ SELECCI\acute{O}N\ GIT}$$
