# INFORME DE COBERTURA DE FORMATOS, AISLAMIENTO Y VALIDACIÓN EN MODO SOMBRA (CANÓNICO)

**Fecha de Corte:** 2026-09-10
**Rama:** `codex/mejoras-pendientes-20260826`
**HEAD Verificado:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
**Remoto:** `https://github.com/joserossel-dot/homologacion-balances.git`
**Entorno Verificado:** macOS / Python 3.14.5 (Poetry venv) / pytest 8.4.2 / fpdf2 2.8.2 / openpyxl 3.1.5 / pdfplumber 0.11.10
**Calidad Estática:** Ruff (0 errores) / Mypy (`--explicit-package-bases`, 0 errores) / compileall (0 errores) / git diff --check (0 errores)

---

## 1. Verificación Inicial de Entorno y Git

- **Ruta del Proyecto Operativo:** `.` (directorio raíz del proyecto)
- **Carpeta Histórica (Referencia de Solo Lectura):** `../homologacion-balances`
- **Rama:** `codex/mejoras-pendientes-20260826`
- **HEAD:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
- **Estado de Trabajo:** Se preservó la modificación preexistente en `docs/ROADMAP_PRODUCCION_ONPREMISE.md`. Se respetó estrictamente la prohibición de tocar código productivo (`parser_universal.py`, `app_validacion.py`, `pipeline/`, etc.), bases de datos remotas (Neon) y diccionarios oficiales (`diccionario.json`, `catalogo_maestro.json`).
- **Ámbitos de Escritura Exclusivos:** `experiments/`, `tests/experiments/`, `reports/`, `pyproject.toml`, `poetry.lock` y `.gitignore`.

---

## 2. Frente 1: Aislamiento en Proceso Limpio y Protección de Red

### 2.1 Importaciones Diferidas y Bloqueo Fail-Closed
1. En `benchmark_classifier_isolated.py`, `benchmark_runner.py` y `shadow_extractor.py`, las importaciones de `HomologationPipeline`, `app_validacion`, `MotorHibridoLocal`, `ParserPDF` y extractores se difirieron para ejecutarse exclusivamente **dentro** del bloque protegido `with isolated_benchmark_environment():`.
2. Se verificó que:
   - Antes del bloque, los módulos productivos no se encuentran en `sys.modules`.
   - Se importan por primera vez bajo aislamiento estricto, sin `DATABASE_URL` ni `NEON_DATABASE_URL` en el entorno.
   - Cualquier intento de conexión a sockets (`socket.socket.connect`, `connect_ex`) lanza un `RuntimeError` fail-closed.
   - Al salir del contexto, las variables de entorno y sockets se restauran exactamente.

### 2.2 Prueba de Aislamiento en Proceso Limpio (`subprocess`)
Se incorporó la prueba `test_benchmark_aislamiento_proceso_limpio_subprocess` en `test_benchmark_isolated.py`, la cual ejecuta un subproceso aislado con `sys.executable` demostrando la hermeticidad total del aislamiento sin contaminar el proceso de pytest.

---

## 3. Frente 2: Eliminación de Filtración de Identificadores

### 3.1 Política de Identificadores y Whitelist Estricta
Se implementó `resolver_doc_id_seguro(ruta_pdf, id_candidato, indice)` en `shadow_extractor.py`:
- **Validación Estricta:** Solo se aceptan identificadores técnicos que cumplan con la expresión regular:
  $$\text{Regex} = \text{\textasciicircum SHADOW-DOC-(?:[0-9]\{2\}-)?[a-f0-9]\{12\}\$}$$
- **Descarte de Texto Libre:** Si el manifiesto contiene nombres de empresas, clientes, RUTs, rutas, correos o espacios, el texto se descarta completamente.
- **Fallback Determinista:** Se genera internamente el digest SHA-256 por bloques de 64 KB sobre el archivo binario completo (`SHADOW-DOC-[idx-]hash[:12]`).
- **Archivos Inexistentes:** Devuelve `SHADOW-DOC-[idx-]NOTFOUND` sin exponer nombres de archivo ni rutas del sistema de archivos.

---

## 4. Frente 3: Refinamiento de Reglas `.gitignore`

Se eliminaron las reglas generales amplias (`*.local.json` y `local_*.json`) que ocultaban indebidamente archivos de configuración ajenos. Se establecieron exclusivamente las reglas específicas requeridas:
- `shadow_manifest.local.json`
- `shadow_manifest.*.local.json`
- `reports/pilot_coverage/local/**`

### Comprobación con `git check-ignore`:
- Archivos ignorados correctamente:
  - `shadow_manifest.local.json` $\rightarrow$ ignorado (regla `.gitignore:99`)
  - `shadow_manifest.cliente.local.json` $\rightarrow$ ignorado (regla `.gitignore:100`)
  - `reports/pilot_coverage/local/run.json` $\rightarrow$ ignorado (regla `.gitignore:101`)
- Archivos NO ignorados (código de salida 1 de `git check-ignore`):
  - `configuracion.local.json`
  - `local_configuracion.json`
  - `manifest_publico.json`

---

## 5. Frente 4: Tratamiento del Orden y Comparación Contable

### 5.1 Semántica Contable vs. Telemetría Diagnóstica
- **Evaluación Contable Multiconjunto:** Las partidas se contrastan mediante multiconjuntos (`Counter`) sobre tuplas completas $(\text{código}, \text{nombre\_norm}, \text{monto}, \text{periodos}, \text{signo}, \text{origen})$.
- **Concordancia:** Si dos extracciones contienen exactamente el mismo multiconjunto de partidas contables pero difieren en el orden secuencial de aparición en el PDF, la clasificación final es **`Concordante`**.
- **Telemetría Diagnóstica:** Se registra la métrica `orden_distinto > 0` con fines de diagnóstico y auditoría, sin penalizar la equivalencia contable.

### 5.2 Matriz de Decisión Final del Modo Sombra
Se verificó exhaustivamente en `test_shadow_decision_final_todos_los_casos_criticos`:
1. **Extracción Idéntica:** `Concordante` (`filas_solo_e1=0`, `filas_solo_e3=0`, `importes_distintos=0`, etc.)
2. **Reordenamiento Puro:** `Concordante` con `orden_distinto >= 1`
3. **Filas solo en E1 / E3:** `Diferente, requiere revisión`
4. **Importes distintos:** `Diferente, requiere revisión`
5. **Signos distintos:** `Diferente, requiere revisión`
6. **Períodos distintos:** `Diferente, requiere revisión`
7. **Orígenes distintos:** `Diferente, requiere revisión`
8. **Controles/Totales distintos:** `Diferente, requiere revisión`
9. **Ambos vacíos:** `No evaluable`
10. **Excepciones técnicas:** `Fallo técnico`

---

## 6. Frente 5: Privacidad y Exclusiones de Archivos

- Se mantuvieron intactos y protegidos los archivos de auditoría previa en `reports/cmcc_review_pipeline/*.xlsx`.
- Durante A12 se detectó que la prueba A11 conservaba identificadores históricos mediante concatenación y se excluía a sí misma del escaneo. A12 eliminó esas referencias y sustituyó el control por patrones genéricos que inspeccionan también el propio archivo de prueba. La comprobación versionable no pretende contener ni enumerar una lista de organizaciones privadas conocidas.
- Todos los fixtures presentes en código y reportes corresponden a marcadores sintéticos explícitamente autorizados (`ENTIDAD_SINTETICA_001`, `usuario_prueba`, `empresa-inexistente.example`, `76.123.456-7`, etc.).

---

## 7. Resumen de Ejecución y Reproducibilidad

### 7.1 Ejecución en Entorno Local
Comando ejecutado:
```bash
poetry run python -m pytest -q tests/experiments/pilot_coverage/
```
Resultado:
```
73 passed, 1 skipped, 4 xfailed in 10.56s
```

### 7.2 Reproducibilidad desde Clon Limpio en Directorio Temporal Aislado
La reproducibilidad de la suite experimental fue comprobada en un árbol temporal limpio instalado desde `poetry.lock` (`/private/var/folders/.../clean_repro_check_*`):
- **Resultado Suite Experimental:** 73 passed, 1 skipped, 4 xfailed (código de salida 0).
- **Alcance de la Verificación:** La regresión integral (1.562 pruebas) fue comprobada en el worktree operativo, pero no fue repetida dentro del entorno temporal limpio.
- **Limpieza:** Directorio temporal eliminado de forma segura tras la prueba.

### 7.3 Detalle de Resultados Experimentales:
- **Total Pruebas Recolectadas:** 78
- **Aprobadas (Passed):** 73
- **Omitidas (Skipped):** 1 (`test_aceptacion_10_xls_antiguo_declaracion_no_probado` $\rightarrow$ Formato XLS binario no soportado declarado explícitamente).
- **Defectos Documentados (XFail Estricto):** 4
  - Formato 01 con extractor histórico original `double_column.py` (falla superada por E3).
  - Formato 04 (balance comparativo que incluye fila de encabezado como cuenta).
  - Formato 05 (balance con notas que fusiona número de nota con descripción).
  - Formato 06 (balance con descripciones multilínea fragmentadas).
- **Fallidas (Failed):** 0
- **XPass Inesperados:** 0

---

## 8. Recomendación Operativa

1. **Uso de E3 en Modo Sombra Pasivo:**
   - La variante experimental E3 se encuentra completamente estabilizada, probada y aislada.
   - Debe ejecutarse exclusivamente en modo sombra pasivo para recopilar telemetría comparativa sin sustituir el parser productivo.
2. **Preservar Parser Productivo E1:**
   - Mantener E1 en la ruta productiva hasta que los resultados comparativos en modo sombra acumulen evidencia estadística suficiente en los balances reales del piloto.
