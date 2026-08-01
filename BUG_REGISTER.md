# BUG_REGISTER.md

> Fecha: 2026-07-26
> Generado mediante inspección directa del código fuente, ejecución de tests y análisis de dependencias.

---

## CRÍTICOS

### C-1: `app_validacion.py` no tiene tests automatizados

- **Archivo**: `app_validacion.py` (1340 líneas)
- **Descripción**: La entrada principal del sistema (Streamlit UI + toda la lógica de clasificación, revisión, propagación y gold standard) carece de cualquier test automatizado. No hay un solo archivo `test_app_validacion.py` en el repositorio.
- **Impacto**: Cualquier cambio en la UI o en la lógica de clasificación puede introducir regresiones sin detección. La propagación automática entre balances (líneas 540-570) y el flujo de metadata no tienen verificación.
- **Recomendación**: Crear tests unitarios para `MotorHibridoLocal.clasificar()`, `propagar_clasificacion_resultados()`, `_extraer_cuentas()`, `parsear_excel()`. Agregar tests de integración con Streamlit (playwright o similar).

### C-2: `parser_universal.py` no tiene tests directos

- **Archivo**: `parser_universal.py` (831 líneas)
- **Descripción**: El parser core del sistema no tiene tests unitarios directos. No existe `test_parser_universal.py`. Las funciones críticas `parsear_linea()`, `detectar_formato_codigo()`, `detectar_separador_miles()`, `validar_archivo()`, y toda la clase `ParserPDF` no tienen verificación automatizada de su comportamiento.
- **Impacto**: Regresiones en el parseo de PDFs/Excel no son detectables. La lógica de OCR fallback, detección de rotación y asignación de columnas no está cubierta.
- **Recomendación**: Tests unitarios para cada función pura (`parsear_linea`, `detectar_formato_codigo`, `detectar_separador_miles`, `validar_archivo`, `parsear_monto`, `normalizar_codigo_ocr`). Tests de integración con PDFs reales del dataset.

### C-3: Dos pipelines de clasificación en producción sin cobertura de test

- **Archivos**: `app_validacion.py:20` (`USE_LEGACY_ENGINE`), `pipeline/homologation_pipeline.py`
- **Descripción**: La aplicación tiene dos pipelines de clasificación completos (MotorHibridoLocal y HomologationPipeline) seleccionables mediante un flag booleano. No hay tests que verifiquen que ambos producen resultados equivalentes. El ShadowMode (`SHADOW_MODE=True`) intenta compararlos pero no tiene aserciones ni alertas.
- **Impacto**: El pipeline legacy (MotorHibridoLocal) y el nuevo (HomologationPipeline) pueden divergir sin que nadie lo note. La decisión de cuál usar depende de un flag en `app_validacion.py:20` sin cobertura.
- **Recomendación**: Tests de regresión que comparen salidas de ambos pipelines sobre el mismo dataset. Estandarizar a un solo pipeline.

### C-4: 11 tests fallidos en `test_split_ac01.py`

- **Archivo**: `tests/test_split_ac01.py`
- **Descripción**: 11 tests fallan consistentemente en el módulo `split_ac01`. Los errores incluyen `AssertionError`, `KeyError` y archivos no generados.
- **Impacto**: El módulo `split_ac01` no es confiable. Los reportes generados están rotos.
- **Recomendación**: Corregir los tests o marcar el módulo completo como no listo para producción.

---

## ALTOS

### A-1: Feature flags sin documentación ni tests de activación

- **Archivos**: `parser_universal.py:15-22`, `pipeline/features.py`, `app_validacion.py:20`
- **Descripción**: Existen 8+ feature flags (`ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER`, `ENABLE_CMCC`, `ENABLE_SEMANTIC_MATCHER`, `ENABLE_DECISION_ENGINE`, `ENABLE_REGEX_FALLBACK`, `USE_LEGACY_ENGINE`, `SHADOW_MODE`) que controlan el comportamiento del pipeline. Ningún test verifica el comportamiento en las diferentes combinaciones de flags. No hay documentación de la matriz de configuración soportada.
- **Impacto**: Combinaciones no testeadas de flags pueden producir comportamientos inesperados en producción. El cambio de un flag puede activar/desactivar funcionalidad completa sin que los tests lo detecten.
- **Recomendación**: Tests parametrizados para las combinaciones críticas de flags. Documentar la matriz de configuración.

### A-2: Dead code: `pipeline/new_pipeline.py` (clase `NewPipeline`)

- **Archivo**: `pipeline/new_pipeline.py`
- **Descripción**: La clase `NewPipeline` está completamente definida pero nunca es importada por ningún otro archivo del repositorio. No aparece en `app_validacion.py`, `homologation_pipeline.py`, ningún test ni script.
- **Impacto**: Código muerto que crea ruido y puede confundir sobre cuál es el pipeline activo.
- **Recomendación**: Eliminar o documentar explícitamente como obsoleto.

### A-3: `reglas_especiales.py` y `clasificador_codigo_cuenta.py` sin tests

- **Archivos**: `reglas_especiales.py`, `clasificador_codigo_cuenta.py`
- **Descripción**: Dos componentes críticos del pipeline (reglas D1-D5 y clasificador por código) no tienen tests directos. Son utilizados tanto por MotorHibridoLocal como por HomologationPipeline.
- **Impacto**: Cambios en la lógica de clasificación o en reglas especiales pueden alterar resultados sin detección.
- **Recomendación**: Tests unitarios para cada regla D1-D5 y para `ClasificadorCodigo.clasificar()`.

### A-4: `config/release.yml` no es leído por ningún código

- **Archivo**: `config/release.yml`
- **Descripción**: Define gates de release (coverage_drop_pct, accuracy_drop_pct, parser_confidence_min, etc.) pero ningún archivo Python lo lee o procesa. Existe `release_pipeline/` pero lee sus propias configuraciones, no este YAML.
- **Impacto**: Los gates de calidad definidos no se aplican. No hay verificación automática antes de releases.
- **Recomendación**: Integrar `release_pipeline/` con `config/release.yml` o eliminar el archivo.

### A-5: `reports/` con 5000+ archivos sin limpieza

- **Archivo**: `reports/` (80+ subdirectorios, 5000+ archivos)
- **Descripción**: El directorio `reports/` contiene una acumulación masiva de reportes de benchmarks, validaciones, auditorías, sombras, etc. Muchos son resultados de ejecuciones únicas (por ejemplo, `cmcc_validation_final/` con 200+ baselines en JSON, `cmcc_benchmark/` con 500+ candidatos).
- **Impacto**: Consumo de espacio en disco, confusión sobre qué reportes son actuales vs históricos, posible inclusión en backups.
- **Recomendación**: Implementar política de retención o limpieza automatizada.

---

## MEDIOS

### M-1: `gold_standard_bench.db` vacía

- **Archivo**: `gold_standard_bench.db`
- **Descripción**: Base de datos de benchmark del gold standard con 0 registros en todas las tablas. Probablemente creada pero nunca poblada.
- **Impacto**: Si algún proceso intenta leerla, obtendrá resultados vacíos sin error.
- **Recomendación**: Poblarla o eliminarla.

### M-2: Diccionarios inconsistentes (3 versiones divergentes)

- **Archivos**: `diccionario.json` (826 entries), `diccionario_actualizado.json` (781), `diccionario_optimizado.json` (712)
- **Descripción**: Existen 3 versiones del diccionario con diferencias de hasta 114 entradas (13.8%). No está documentado cuál es la fuente de verdad ni cómo se sincronizan.
- **Impacto**: El pipeline usa `diccionario.json` (hardcodeado en `HomologationPipeline._load_dictionary()`), pero `app_validacion.py` permite descargar "diccionario actualizado" que escribe sobre el mismo archivo. Podría haber pérdida de datos.
- **Recomendación**: Unificar a una sola versión. El resto debe ser histórico.

### M-3: `learning_queue.json` no integrado en el pipeline

- **Archivo**: `learning_queue.json` (registro de correcciones)
- **Descripción**: `LearningEngine` persiste correcciones humanas en `learning_queue.json`, pero este archivo nunca es leído para realimentar el Gold Standard o el diccionario de forma automática.
- **Impacto**: Las correcciones humanas se almacenan pero no se aprovechan para mejorar el pipeline.
- **Recomendación**: Implementar un proceso que revise la cola y actualice el Gold Standard periódicamente.

### M-4: `review_ui/reviews.db` con 251 decisiones no visibles desde la app

- **Archivo**: `review_ui/reviews.db`
- **Descripción**: La base de datos de `review_ui` contiene 251 decisiones de revisión, pero no hay integración con `app_validacion.py`. Solo es accesible mediante `scripts/run_human_review.py`.
- **Impacto**: Datos de revisión humana existentes pero no utilizados para mejoras ni visibles desde la interfaz principal.
- **Recomendación**: Conectar review_ui con el flujo de correcciones y gold standard.

### M-5: Tests que exceden timeout (varios archivos)

- **Archivos**: `test_knowledge_discovery.py`, `test_semantic.py`, `test_dictionary_audit.py`, `test_confidence_audit.py`, `test_review_package.py`, `test_gold_import.py`, `test_quality_monitoring.py`, `test_release_pipeline.py`, `test_knowledge_evolution.py`, `test_account_type_filter.py`, `test_api_compatibility.py`, `test_regex_fallback.py`, `test_scientific_validation.py`, `test_decision_trace.py`
- **Descripción**: Al menos 14 archivos de test (tanto en root como en `tests/`) exceden el timeout de 60-120 segundos cuando se ejecutan en conjunto. Esto sugiere que contienen operaciones lentas (posiblemente I/O, PDF real, o bucles grandes) o dependencias externas no disponibles.
- **Impacto**: La suite completa no se puede ejecutar de forma confiable. Cobertura de CI/CD comprometida.
- **Recomendación**: Identificar tests lentos, marcar como `@pytest.mark.slow`, separar tests unitarios de integración.

### M-6: `pyproject.toml` referencia `src.cli:main` que no existe

- **Archivo**: `pyproject.toml:20`
- **Descripción**: `[tool.poetry.scripts]` define `carpeta-tributaria = "src.cli:main"` pero `src/cli.py` no existe en el repositorio.
- **Impacto**: `poetry run carpeta-tributaria` falla con `ModuleNotFoundError`.
- **Recomendación**: Crear el CLI o eliminar la referencia.

---

## BAJOS

### B-1: `.env` contiene dos veces la misma variable

- **Archivo**: `.env`
- **Descripción**: `DATABASE_URL` aparece dos veces con el mismo valor. La segunda está comentada como "ENTORNO LOCAL DE DESARROLLO".
- **Impacto**: Confusión sobre cuál es la configuración activa. Riesgo de exponer credenciales en el repositorio (`.env` está en `.gitignore`, pero la plantilla está visible).
- **Recomendación**: Limpiar duplicación, documentar claramente.

### B-2: `Dockerfile` usa `poetry config virtualenvs.create false`

- **Archivo**: `Dockerfile`
- **Descripción**: La instalación en Docker desactiva entornos virtuales, lo que puede causar conflictos de dependencias con paquetes del sistema.
- **Impacto**: Potenciales conflictos de versiones en el contenedor Docker.
- **Recomendación**: Usar `poetry install --no-root` con virtualenv, o usar `pip install` directamente desde `requirements.txt`.

### B-3: `scipy` importado pero no en dependencias

- **Archivo**: `knowledge/variant_discovery/` (varios archivos)
- **Descripción**: `scipy.spatial.distance` y `scipy.cluster.hierarchy` se usan en el módulo de variant_discovery, pero `scipy` no aparece en `pyproject.toml` ni `requirements.txt`.
- **Impacto**: El módulo falla en instalaciones fresh con `ModuleNotFoundError: No module named 'scipy'`.
- **Recomendación**: Agregar `scipy` a las dependencias o refactorizar para no depender de él.

### B-4: 8 archivos `.py` standalone en root sin uso claro

- **Archivos**: `analyze_formats.py`, `inspect_pdf.py`, `run_semantic_shadow.py`, `run_audit.py`, `summarize_formats.py`, `validate_families.py`, `analyze_formats.py`, `run_knowledge_discovery.py`, `run_knowledge_generator.py`
- **Descripción**: Archivos Python en la raíz del proyecto que son scripts independientes. No está claro si son herramientas de desarrollo, análisis o legacy.
- **Impacto**: Contaminación del directorio raíz, confusión sobre punto de entrada.
- **Recomendación**: Mover a `scripts/` o eliminar si son obsoletos.

### B-5: `Setting` archivo vacío en root

- **Archivo**: `Setting`
- **Descripción**: Archivo vacío de 0 bytes en la raíz del proyecto.
- **Impacto**: Confusión sobre su propósito.
- **Recomendación**: Eliminar.
