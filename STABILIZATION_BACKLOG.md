# STABILIZATION_BACKLOG.md

> Solo bugs, deuda técnica imprescindible y riesgos para producción.
> Priorización: P0 = bloqueante, P1 = alto, P2 = medio, P3 = bajo.

---

## BUGS

| ID | Prioridad | Descripción | Archivo(s) | Evidencia |
|---|---|---|---|---|
| B-01 | **P0** | 11 tests fallan en `split_ac01` (`AssertionError`, `KeyError`) | `tests/test_split_ac01.py` | Ejecución: 11 failed of 252 tests |
| B-02 | **P1** | `pyproject.toml` referencia `src.cli:main` que no existe | `pyproject.toml:20` | `poetry run carpeta-tributaria` → `ModuleNotFoundError` |
| B-03 | **P1** | `scipy` importado en `knowledge/variant_discovery/` pero no en dependencias | `knowledge/variant_discovery/clusterer.py`, `pyproject.toml` | `ModuleNotFoundError` en instalación fresh |
| B-04 | **P2** | `gold_standard_bench.db` vacía (0 registros) | `gold_standard_bench.db` | `SELECT COUNT(*) → 0` en todas las tablas |
| B-05 | **P2** | `learning_queue.json` nunca retroalimenta el Gold Standard | `learning_queue.json`, `learning/engine.py` | Revisión de código: no hay proceso que lea el queue para actualizar GS |
| B-06 | **P3** | `.env` tiene `DATABASE_URL` duplicada | `.env` | Inspección directa del archivo |
| B-07 | **P3** | `Setting` archivo vacío de 0 bytes en root | `Setting` | `ls -la` muestra archivo vacío |

---

## DEUDA TÉCNICA IMPRESCINDIBLE

| ID | Prioridad | Descripción | Archivo(s) | Líneas | Evidencia |
|---|---|---|---|---|---|
| T-01 | **P0** | **Sin tests para `app_validacion.py`** (1340 líneas, el archivo más grande del proyecto) | `app_validacion.py` | 1340 | No existe `test_app_validacion.py` en el repositorio |
| T-02 | **P0** | **Sin tests para `parser_universal.py`** (831 líneas, parser core del sistema) | `parser_universal.py` | 831 | No existe `test_parser_universal.py` en el repositorio |
| T-03 | **P0** | **Dos pipelines de clasificación activos** sin tests de equivalencia | `app_validacion.py:20`, `pipeline/homologation_pipeline.py` | — | `USE_LEGACY_ENGINE` flag sin cobertura |
| T-04 | **P1** | **Dead code**: `pipeline/new_pipeline.py` (clase `NewPipeline` nunca importada) | `pipeline/new_pipeline.py` | ~100 | `grep -r "new_pipeline" *.py tests/ scripts/` → 0 resultados externos |
| T-05 | **P1** | **Sin tests para `reglas_especiales.py`** (reglas D1-D5 crediticias) | `reglas_especiales.py` | — | No existe test directo en `tests/` |
| T-06 | **P1** | **Sin tests para `clasificador_codigo_cuenta.py`** (clasificador por código) | `clasificador_codigo_cuenta.py` | — | No existe test directo en `tests/` |
| T-07 | **P1** | **8 feature flags** sin documentación ni tests de activación | `parser_universal.py:15-22`, `pipeline/features.py` | — | `ENABLE_DYNAMIC_LAYOUT=False`, `ENABLE_ACCOUNT_TYPE_RESOLVER=False`, etc. |
| T-08 | **P1** | **`config/release.yml`** no es leído por ningún código | `config/release.yml` | — | Gates de release no se aplican |
| T-09 | **P1** | **3 diccionarios inconsistentes** (826 vs 781 vs 712 entradas) | `diccionario.json`, `diccionario_actualizado.json`, `diccionario_optimizado.json` | — | Diferencias de hasta 13.8% sin documentación |
| T-10 | **P2** | **14+ archivos de test** exceden timeout (suite completa no ejecutable) | `test_knowledge_discovery.py`, `test_semantic.py`, `test_dictionary_audit.py`, etc. | — | Ejecución con `-x` timeout > 2 minutos |
| T-11 | **P2** | **8 scripts standalone en root** sin organización | `analyze_formats.py`, `inspect_pdf.py`, `run_semantic_shadow.py`, etc. | — | Contaminan directorio raíz, propósito no documentado |
| T-12 | **P2** | **`reports/` con 5000+ archivos** sin política de retención | `reports/` | 5000+ | Acumulación histórica sin limpieza |
| T-13 | **P2** | **`review_ui/reviews.db`** con 251 decisiones no conectadas a la app | `review_ui/reviews.db`, `app_validacion.py` | 251 rows | Datos existentes no aprovechados |
| T-14 | **P3** | `Dockerfile` usa `virtualenvs.create false` | `Dockerfile` | 1 línea | Riesgo de conflictos de dependencias |
| T-15 | **P3** | `Setting` archivo vacío en root | `Setting` | 0 bytes | Eliminar |

---

## RIESGOS PARA PRODUCCIÓN

| ID | Prioridad | Riesgo | Descripción | Mitigación |
|---|---|---|---|---|
| R-01 | **P0** | **Sin cobertura de tests para el flujo principal** | `app_validacion.py` (1340 líneas) zero tests. Cualquier cambio en la UI o lógica de clasificación puede romper producción sin detección. | Crear tests antes de cualquier modificación. |
| R-02 | **P0** | **Parser sin tests** | `parser_universal.py` (831 líneas) sin tests directos. El componente que extrae datos financieros de PDFs no tiene verificación. | Tests unitarios para funciones de parseo. |
| R-03 | **P1** | **Dos pipelines pueden divergir** | `USE_LEGACY_ENGINE=False` por defecto, pero el legacy sigue presente. ShadowMode no alerta sobre divergencias mayores. | Unificar a un solo pipeline. |
| R-04 | **P1** | **Regresiones silenciosas por feature flags** | 8 combinaciones de flags no testeadas. Cambiar un flag puede activar código no probado. | Tests parametrizados. |
| R-05 | **P1** | **Diccionario inconsistente** | `diccionario.json` (canonical) vs `diccionario_optimizado.json` (usado por pipeline) difieren en 114 entradas. La clasificación depende de cuál se use. | Unificar y documentar fuente de verdad. |
| R-06 | **P2** | **Gold Standard no retroalimentado** | 187 registros en gold_standard.db y 251 decisiones en review_ui/reviews.db no se usan para mejorar automáticamente. El sistema no aprende de correcciones. | Implementar ciclo de retroalimentación. |
| R-07 | **P2** | **Suite de tests no ejecutable completamente** | Múltiples tests exceden timeout. No es posible verificar el estado completo del sistema antes de un deploy. | Identificar y marcar tests lentos (`@pytest.mark.slow`). |
| R-08 | **P2** | **Dependencia `scipy` faltante** | `knowledge/variant_discovery/clusterer.py` importa `scipy` no declarado. El módulo falla en instalación fresh. | Agregar a `pyproject.toml`. |
| R-09 | **P2** | **Módulos ORPHANED pueden estar rotos** | `confidence/`, `evidence/`, `knowledge_base/`, `accounting_knowledge/`, `assessment/` no tienen consumidores. Su estado de funcionamiento es desconocido. | Decidir: integrar, eliminar, o documentar como legacy. |
| R-10 | **P3** | **Endpoint FastAPI no usado** | `src/api/main.py` existe pero no hay cliente ni ruta de producción que lo use. | Decidir si es necesario o eliminarlo. |

---

## Resumen de cargas de trabajo

| Categoría | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|
| Bugs | 1 | 2 | 2 | 2 | 7 |
| Deuda técnica | 3 | 6 | 5 | 2 | 15 |
| Riesgos | 2 | 3 | 4 | 1 | 10 |
| **Total** | **6** | **11** | **11** | **5** | **33** |
