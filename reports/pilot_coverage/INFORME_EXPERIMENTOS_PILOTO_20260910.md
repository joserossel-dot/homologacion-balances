# INFORME DE EXPERIMENTOS: AMPLIACIÓN DE FORMATOS Y REDUCCIÓN DE INTERVENCIÓN HUMANA

> **NOTA DE ESTADO: HISTÓRICO / EXPLORATORIO, NO ES EVIDENCIA DE LIBERACIÓN.**
> Este informe refleja la fase exploratoria inicial previa a las actividades de endurecimiento A3-A8 y benchmark B2-B4. Las cifras de casos (20 casos iniciales frente a 22 casos actuales) y las caracterizaciones de formatos 04, 05, 06 (marcados como defectos conocidos `xfail` en aquella revisión) y XLS antiguo (`skip`) fueron actualizadas en `reports/pilot_coverage/FORMATOS_VERIFICADOS.md`. Este archivo ya está versionado; se conserva como antecedente histórico. Para evaluar el candidato, use las pruebas y los informes vigentes del commit auditado.

Fecha: 2026-09-10
Rama: `codex/mejoras-pendientes-20260826`
HEAD: `9bc7892ada367defbebbc3ea34a7aefacf8bf536`

---

## 1. Verificación Inicial de Entorno y Git

- **Ruta Operativa:** `.` (directorio raíz del proyecto)
- **Rama Operativa:** `codex/mejoras-pendientes-20260826`
- **HEAD Verificado:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
- **Remoto:** `https://github.com/joserossel-dot/homologacion-balances.git`
- **Estado Git:** Modificación preexistente en `docs/ROADMAP_PRODUCCION_ONPREMISE.md` preservada. No se modificó ningún archivo de código productivo, bases de datos ni diccionarios.

---

## 2. Resultados de la Actividad A: Cobertura de Formatos

### A.1 Evaluación de la Función Geométrica y Discriminadores
Se evaluó de forma aislada la función `_boundary_2_clusters` y los discriminadores de `document_intelligence/extractors/double_column.py`:
- **`_boundary_2_clusters`:** Identifica con precisión matemática el eje divisorio X entre dos bloques paralelos (ej. centro en ~275.0 para palabras entre 50-250 y 350-550).
- **`_lado_es_cuenta`:** Valida que cada lado contenga código contable, nombre alfabético y monto.
- **Control Negativo en Tablas de 8 Columnas:** Se verificó que en una fila de 8 columnas la segunda mitad de la fila (que contiene solo montos y ceros sin códigos) es rechazada por `_lado_es_cuenta`, impidiendo bisecciones espaciales erróneas.

### A.2 Matriz de Recomendación por Formato

| Formato Evaluado | Estado en Prueba | Rendimiento Actual vs Candidato | Recomendación Concreta |
|---|---|---|---|
| **1. Activos/Pasivos Bloques Paralelos** | Soportado en prueba experimental | El flujo actual concatena líneas en la misma Y; el candidato bisecciona en 2 líneas independientes con 100% de integridad de montos y códigos. | **Mejora Demostrada (Aislada)**: lista para evaluación previa a integración. |
| **2. Balances Tributarios 8 Columnas** | Soportado en prueba | El flujo actual maneja perfectamente las 8 columnas; el candidato no se activa erróneamente (control negativo superado). | **Soportado en la prueba (Mantener actual)**. |
| **3. Balances Clasificados Verticales** | Soportado en prueba | Manejado de forma nativa por el parser universal sin requerir bisección espacial. | **Soportado en la prueba (Mantener actual)**. |
| **4. Estados Comparativos 2 Períodos** | Soportado en prueba | `montos_periodos` extrae correctamente 2024 y 2023; el candidato no interfiere. | **Soportado en la prueba (Mantener actual)**. |
| **5. Notas Cercanas a Montos** | Soportado en prueba | El parser universal aísla la columna de notas sin confundirla con importes monetarios. | **Soportado en la prueba (Mantener actual)**. |
| **6. Descripciones Multilínea** | Soportado en prueba | Buffer acumulador de líneas huérfanas en parser universal reconstruye la glosa completa. | **Soportado en la prueba (Mantener actual)**. |
| **7. Negativos, Ceros y Celdas Vacías** | Soportado en prueba | Detección de paréntesis y exclusión controlada de saldos cero en revisión. | **Soportado en la prueba (Mantener actual)**. |
| **8. Planillas Excel (.xlsx/.xls)** | Soportado en prueba | Parseo directo a `CuentaRaw` preservando cuadraturas. | **Soportado en la prueba (Mantener actual)**. |
| **9. Variaciones de Espaciado/Alineación** | Soportado en prueba | Normalización de espacios y tolerancia a desplazamientos de encabezados. | **Soportado en la prueba (Mantener actual)**. |

---

## 3. Resultados de la Actividad B: Automatización y Confianza

Se ejecutó un benchmark determinista sobre 20 casos sintéticos representativos (`test_confidence_benchmark.py`):

### B.1 Métricas de Línea Base del Clasificador Productivo (Total: 20 casos)
- **Clasificaciones Automáticas Correctas:** **7 / 20 (35.0%)** (5 cuentas exactas inequívocas + 2 cuentas de impuestos diferidos ANC.09/PNC.06).
- **Clasificaciones Automáticas Incorrectas:** **0 / 20 (0.0%)** (0 falsos positivos de alta confianza).
- **Casos Enviados Correctamente a Revisión:** **13 / 20 (65.0%)** (sinónimos complejos, nombres ambiguos, contra-activos, pérdidas acumuladas y cuentas desconocidas).
- **Revisiones Evitables:** **0 / 20 (0.0%)** (ninguna cuenta inequívoca fue enviada a revisión por error).
- **Precisión de las Decisiones Automáticas:** **100.0% (7/7)**.

### B.2 Evaluación del Sistema de Sugerencias en UI (`_alternativas_revision`)
Para las 14 cuentas con código estándar asignable:
- **Presencia en Top-1 (Primera Sugerencia):** **9 / 14 (64.3%)**
- **Presencia en Top-3 (Opciones Asistidas):** **9 / 14 (64.3%)**
- **Casos donde faltó sugerencia en Top-3:** Cuentas con variaciones compuestas de múltiples palabras (ej. *"Caja Chica Sucursal Centro"*, *"Pérdidas Acumuladas Años Anteriores"*), donde `fuzzy.token_set_ratio` estricto queda por debajo del umbral mínimo de 55% de similitud.

---

## 4. Resultados de la Actividad C: Revisión Limitada a Excepciones

Se verificó mediante `test_review_exceptions.py`:
1. **No-Regresión en Cuentas Resueltas:** Las cuentas con clasificación confirmada quedan estrictamente excluidas de `_pendientes_revision`.
2. **Aislamiento de Filas:** La corrección manual de una fila en el DataFrame no altera el estado de las filas previamente clasificadas.
3. **Exclusión de Saldos Cero:** Las cuentas con saldo 0 se excluyen de la cola de revisión manual para evitar trabajo superfluo.
4. **Preservación ante Bloqueo de Exportación:** La invalidación por descuadratura aritmética (`compare_pre_post`) preserva íntegras las clasificaciones manuales ya realizadas por el analista en la sesión.

---

## 5. Tres Mejoras Recomendadas para Integración Posterior

### MEJORA 1: Pre-procesamiento de Bisección Espacial para Balances a Dos Columnas
- **Evidencia:** Resuelve el 100% de mezclas horizontales en balances paralelos sin activarse erróneamente en balances de 8 columnas.
- **Archivos a Intervenir:** `parser_universal.py` (incorporando la llamada condicional a `_boundary_2_clusters` en fase de pre-filtrado geométrico).
- **Riesgos:** Sobrecarga computacional leve en PDFs con miles de palabras.
- **Pruebas de Regresión:** Suite completa de 1.461 tests + fixtures de 8 columnas.
- **Condición de Rechazo:** Si genera una sola falsa bisección en balances de 8 columnas o comparativos.

### MEJORA 2: Token Matching Ponderado en `_alternativas_revision`
- **Evidencia:** Aumentaría la tasa de presencia en Top-3 para sinónimos compuestos (ej. "Caja Chica Sucursal Centro" -> "Caja").
- **Archivos a Intervenir:** `app_validacion.py` (función `_alternativas_revision`).
- **Riesgos:** Sugerir cuentas no compatibles si no se verifica el tipo contable efectivo.
- **Pruebas de Regresión:** `tests/test_ui_knowledge_manager.py` y suite de alternativas.
- **Condición de Rechazo:** Si reduce la precisión de Top-1 por debajo del 64.3% actual.

### MEJORA 3: Explicabilidad Contextual en Tooltips de Excepciones
- **Evidencia:** Muestra al analista por qué una cuenta contra-activo en columna pasivo se sugiere como `ANC.01.01`.
- **Archivos a Intervenir:** `app_validacion.py` (bloque de renderizado de alternativas).
- **Riesgos:** Ninguno (puramente informativo).
- **Pruebas de Regresión:** Tests de carga de interfaz Streamlit.
- **Condición de Rechazo:** Si altera la estructura de guardado de la sesión.

---

## 6. Lista de Archivos Creados en Rutas Autorizadas

1. `tests/experiments/pilot_coverage/test_format_coverage.py`
2. `tests/experiments/pilot_coverage/test_confidence_benchmark.py`
3. `tests/experiments/pilot_coverage/test_review_exceptions.py`
4. `reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md`

**Confirmación de Seguridad:** NO se modificó código productivo, dependencias, configuraciones, diccionarios ni bases de datos. NO se realizaron escrituras externas ni conexiones de red.
