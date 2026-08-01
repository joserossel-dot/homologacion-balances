# Análisis de Flujo de Ejecución en Tiempo Real

**Fecha:** 2026-07-28  
**Propósito:** Mapear exactamente qué ocurre desde que un usuario sube un archivo hasta que se genera la salida.

---

## Flujo Real Actual (app_validacion.py)

### RUTA 1: Flujo Legacy (`USE_LEGACY_ENGINE = True`)

```
USUARIO
  │
  ├── sidebar: file_uploader(type=['pdf','xlsx','xls'])
  │     archivos = st.file_uploader(...)
  │
  ├── sidebar: selectbox("Giro de la empresa")
  │     giro_norm = None | giro.lower()
  │
  ├── sidebar: st.metric("Cuentas en diccionario", len(st.session_state.diccionario))
  ├── sidebar: st.metric("Códigos en catálogo", len(catalogo))
  ├── sidebar: download_button("Descargar diccionario actualizado") [si hay correcciones]
  │
  ├── if not archivos → mostrar resumen catálogo, return
  │
  ├── if not metadata_confirmada:
  │     _extraer_lineas_encabezado(first_file)
  │     extraer_metadata(lineas_encabezado) → MetadataEmpresa(rut, razon_social, giro)
  │     Formulario empresa (RUT, Razón Social, Giro)
  │     Confirmar → st.rerun()
  │
  ├── metadata_confirmada = True:
  │     ┌─────────────────────────────────────────────────────────────┐
  │     │ POR CADA archivo nuevo (no en st.session_state.resultados) │
  │     │                                                             │
  │     │  1. _extraer_lineas_encabezado(archivo)                     │
  │     │     pdfplumber → primeras 40 líneas de texto                │
  │     │     Data producida: list[str] (líneas de texto)             │
  │     │     Consumido por: extraer_metadata()                      │
  │     │                                                             │
  │     │  2. extraer_metadata(lineas_encabezado)                     │
  │     │     Data producida: MetadataEmpresa(rut, razon, periodo,    │
  │     │                      giro, confianza)                       │
  │     │     Almacenado en: st.session_state.metadata_files[name]    │
  │     │                                                             │
  │     │  3. _extraer_cuentas(archivo):                              │
  │     │     PDF → ParserPDF.parsear(tmp_path)                        │
  │     │       → validar_archivo()                                   │
  │     │       → _extraer_lineas() [pdfplumber | OCR]                │
  │     │       → detectar_formato_codigo()                           │
  │     │       → detectar_separador_miles()                          │
  │     │       → parsear_linea() × N                                 │
  │     │       → ResultadoParseo(cuentas=[CuentaRaw])                │
  │     │     Excel → parsear_excel(archivo)                          │
  │     │       → pandas.read_excel → [CuentaRaw]                     │
  │     │                                                             │
  │     │  4. MotorHibridoLocal(diccionario)                          │
  │     │     POR CADA cuenta:                                        │
  │     │       a. ¿Monto None y sin código? → skip                   │
  │     │       b. ¿No código y PATRON_NO_CUENTA? → skip              │
  │     │       c. motor.clasificar(cuenta, giro_norm)                │
  │     │          ├── ¿nombre ambiguo + columna? → clasificación     │
  │     │          ├── ¿código clasificable? → ClasificadorCodigo     │
  │     │          ├── ¿diccionario exacto?                           │
  │     │          ├── ¿diccionario fuzzy? (rapidfuzz)                │
  │     │          ├── ¿regla regex? (REGLAS_COMPILADAS)              │
  │     │          └── _corregir_por_columna()                        │
  │     │          └── reglas_especiales.aplicar() [R1-R5]            │
  │     │                                                             │
  │     │     Data producida: DataFrame con columnas:                 │
  │     │       linea, codigo_original, nombre_original, monto,       │
  │     │       origen_columna, es_total, codigo_clasificado,         │
  │     │       metodo, confianza, requiere_revision, notal,          │
  │     │       confianza_extraccion, origen_columna_display          │
  │     │                                                             │
  │     │  5. SHADOW MODE (solo PDF):                                │
  │     │     HomologationPipeline.process(tmp_pdf)                   │
  │     │     ShadowLogger.log(comparisons, match_rate)               │
  │     │     Data producida: JSON en logs/shadow/{id}.json           │
  │     │     NO AFECTA LA UI                                         │
  │     └─────────────────────────────────────────────────────────────┘
  │
  ├── propagar_entre_balances() [una vez]
  │     Data producida: st.session_state.resultados modificado
  │
  ├── Sidebar: lista de balances cargados
  ├── Sidebar: selectbox archivo activo
  │
  ├── Documento visor: _visor_documento(archivo)
  │     PDF → pdf2image → PNG → base64 → HTML
  │     Excel → pandas → HTML
  │
  ├── Tabs:
  │   ├── 📈 Resumen: _tab_resumen(df) → KPIs
  │   ├── 🔍 Cola de Revisión: _tab_revision(df, catalogo, motor)
  │   │     POR CADA cuenta pendiente:
  │   │       → selectbox clasificación
  │   │       → Confirmar → st.session_state.resultados modificado
  │   │       → _save_gold_standard() → gold_standard.db
  │   │       → Diccionario actualizado → diccionario.json
  │   │       → propagar_clasificacion_resultados()
  │   │     Lote: selección múltiple → clasificación en masa
  │   ├── 📋 Balance Normalizado: _tab_balance(df, catalogo)
  │   │     → Agrupa por codigo_clasificado
  │   │     → Muestra subtotales por categoría
  │   │     → Calcula Patrimonio Efectivo
  │   │     → Exporta Excel (openpyxl)
  │   │     → _validar_cuadre_utilidad()
  │   ├── 📚 Diccionario: _tab_diccionario() → búsqueda + tabla
  │   ├── 🧠 Aprendizaje: _tab_aprendizaje() → GoldBuilder stats
  │   └── 📊 Analytics: placeholder "Work in Progress"
  │
  └── Export: download_button → Excel
```

### RUTA 2: Flujo Nuevo (`USE_LEGACY_ENGINE = False`) — ROTO

```
Igual que Ruta 1 hasta metadata_confirmada.

Luego:
  POR CADA archivo nuevo:
    1. _extraer_lineas_encabezado(archivo)  (igual)
    2. extraer_metadata(lineas_encabezado)   (igual)
    3. _extraer_cuentas(archivo)             (igual)
    4. POR CADA cuenta:
       ab = AccountAdapter.from_cuenta_raw(c)   → AccountBalance
       interp = BalanceInterpreter(ab)          → nature, classification_amount
       
       SI classification_amount is None or 0:
         → "movement_only" (ignorada)
       SINO:
         classification = hp._classify_account(codigo, nombre)
           → LearningEngine.best_match()
           → [si ENABLE_CMCC + ENABLE_CMCC_PRODUCTION] CMCCClassifier
           → [si ENABLE_DECISION_ENGINE] DecisionEngine
           → [si no DE] ClasificadorCodigo → Diccionario exacto → fuzzy → SemanticMatcher → Regex
         
         adjustment = hp._rule_processor.aplicar(nombre, codigo, monto)
         
       Data producida: DataFrame (mismas columnas que flujo legacy)
       
    ¡FALLA! — NameError: name 'time' is not defined (líneas 494, 561)

  propagar_entre_balances() [bloque duplicado, línea 598-623 = código muerto]
```

---

## Módulos Utilizados vs No Utilizados

### Módulos que SÍ participan del flujo actual

| Módulo | Flujo Legacy | Flujo Nuevo | Datos que produce | Datos que consume |
|--------|-------------|-------------|-------------------|-------------------|
| `app_validacion.py` | ✅ | ✅ | UI completa, session_state | Todos los módulos abajo |
| `parser_universal.py` | ✅ | ✅ | `ResultadoParseo(cuentas: [CuentaRaw])` | Archivo PDF |
| `clasificador_codigo_cuenta.py` | ✅ | ✅ | `ResultadoCodigo(codigo_estandar, confianza)` | Código de cuenta (string) |
| `reglas_especiales.py` | ✅ | ✅ | `AjusteEspecial(aplica, codigo_final, flag)` | nombre, código, monto, giro |
| `extractor_metadata.py` | ✅ | ✅ | `MetadataEmpresa(rut, razon, periodo, giro)` | Líneas de texto |
| `gold_standard/builder.py` | ✅ | ✅ | `GoldBuilder` (inserts/updates en DB) | `GoldRecord`, consultas SQL |
| `gold_standard/models.py` | ✅ | ✅ | `GoldRecord` (dataclass) | — |
| `gold_standard/storage.py` | ✅ | ✅ | SQLite connection, tabla gold_records | — |
| `pipeline/homologation_pipeline.py` | ✅* | ✅ | `HomologationPipeline.process()` → dict | Archivo path |
| `adapters/account_adapter.py` | ❌ | ✅ | `AccountBalance` | `CuentaRaw` |
| `interpreters/balance_interpreter.py` | ❌ | ✅ | nature, classification_amount | `AccountBalance` |
| `learning/engine.py` | ❌ | ✅ | `best_match()` → dict | account_name (string) |
| `shadow/shadow_logger.py` | ✅* | ❌ | JSON log file | comparison data |

\* Solo en SHADOW MODE del flujo legacy.

### Módulos que NO participan del flujo actual

| Módulo | Estado | Qué hace | Por qué no se usa |
|--------|--------|----------|-------------------|
| `document_intelligence/` | ❌ No usado | Analiza documento, predice confianza, selecciona parser, recomienda validación | No hay referencia desde app_validacion |
| `structure_engine/` | ❌ No usado | Detecta familia, estructura, plantillas del documento | No hay referencia desde app_validacion |
| `document_context/` | ❌ No usado | Contexto único del documento con write-once sections y lifecycle | app_validacion usa session_state directamente |
| `knowledge_base/` | ❌ No usado | Taxonomía, reglas, validación de conocimiento contable | No hay referencia desde app_validacion |
| `coverage_engine/` | ❌ No usado | Calcula cobertura (monetaria, estructural, semántica) | No hay referencia desde app_validacion |
| `self_qa_engine/` | ❌ No usado | Quality gates, riesgo, confianza, recomendaciones | No hay referencia desde app_validacion |
| `validation/` | ❌ No usado | Validación de balance (ecuación, subtotales, integridad) | app_validacion tiene `_validar_cuadre_utilidad()` inline |
| `review_workspace/` | ❌ No usado | Base de datos de revisión, búsqueda, similitud | No hay referencia desde app_validacion |
| `decision/engine.py` | ❌ No usado en app | Resuelve conflictos SM vs Regex | Usado por HomologationPipeline cuando feature flag activo |
| `decision_engine.py` (root) | ❌ No usado | Rule-based PDF strategy decision | Script independiente |
| `src/core/orquestador.py` | ❌ No usado | PipelineOrquestador (stub) | Nunca integrado |
| `dataset_manager.py` | ❌ No usado | Gestión de datasets para entrenamiento | CLI independiente |
| `context/` | ❌ No usado | Context builder, account context | Preliminar, reemplazado por document_context/ |
| `orchestrator/pipeline_v2.py` | ❌ No usado | HomologationPipelineV2 con DocumentContext | Existe pero NO es llamado desde app_validacion |

---

## Datos Producidos y No Consumidos

| Dato producido por | Qué contiene | ¿Quién lo consume? |
|-------------------|-------------|-------------------|
| `MetadataEmpresa` (extractor_metadata) | RUT, razón social, período, giro | UI (formulario empresa, header del balance) |
| `ResultadoParseo.advertencias` | Advertencias del parsing | UI (st.warning en legacy, ignorado en nuevo flujo) |
| `ShadowLogger` logs | Comparación legacy vs nuevo pipeline | **NADIE** — solo se escribe a disco, nunca se consulta desde UI |
| `gold_standard.db` | Historial de correcciones humanas | Solo `_tab_aprendizaje()` lo consulta. No retroalimenta el pipeline automáticamente |
| Clasificación por método | statistics en UI | Solo se muestran en tab Resumen. No alimentan otro módulo |
| `st.session_state.correcciones` | Lista de correcciones pendientes de descarga | Solo `download_button` |
| `dictionary_matches`, `learning_hits`, `cmcc_matches` en KBAdapter | Listas detalladas de coincidencias | En V1: solo estadísticas en UI. En V2: KnowledgeData los consume |

---

## Duplicaciones en el Flujo

1. **Lógica de clasificación duplicada**: `MotorHibridoLocal` (app_validacion.py:162) vs `HomologationPipeline._classify_by_*` (pipeline/homologation_pipeline.py:107)
2. **Normalización duplicada**: 3 implementaciones (`app_validacion.normalizar_nombre`, `HomologationPipeline._normalize_name`, `learning/exact_match.normalize_name`)
3. **Parsing duplicado**: `_extraer_lineas_encabezado()` y `_extraer_cuentas()` leen el archivo dos veces (PDF: pdfplumber para encabezado, ParserPDF para cuentas)
4. **Propagación duplicada**: `propagar_entre_balances()` definida 2 veces (líneas 570 y 599). La segunda es código muerto.
5. **Filtro de cuentas no contables duplicado**: `PATRON_NO_CUENTA` en app_validacion y `GARBAGE_PATTERNS` en parser_universal
6. **Reglas regex duplicadas**: `REGLAS_REGEX` en app_validacion y `_REGEX_FALLBACK` en homologation_pipeline (subconjunto auditado)
7. **Patrimonio Efectivo**: `calcular_patrimonio_efectivo()` solo se usa en `_tab_balance()`, no hay integración con el pipeline

---

## Flujo V2 Existente (orchestrator/pipeline_v2.py)

```
HomologationPipelineV2.process(pdf_path) → DocumentContext
  │
  ├── 1. SIEAdapter.run(ctx)      → DocumentMetadata, StructureData
  ├── 2. DIEAdapter.run(ctx)      → PredictionData (confianza esperada, cobertura)
  ├── 3. ParserAdapter.run(ctx)   → ParserData (raw_accounts)
  │       Nota: ParserAdapter tiene dependencia circular con app_validacion (importa parsear_excel)
  ├── 4. KBAdapter.run(ctx)         → KnowledgeData, classified, ignored
  │       Nota: KBAdapter tiene dependencia circular (importa HomologationPipeline)
  ├── 5. DecisionAdapter.run(ctx)   → decisions, decision_stats
  │       Dependencia: decision_engine.py (módulo en root, NO decision/engine.py)
  ├── 6. ValidationAdapter.run(ctx) → ValidationData
  ├── 7. ReviewAdapter.run(ctx)     → ExecutionData, review_queue
  ├── 8. CoverageAdapter.run(ctx)   → coverage (custom)
  └── 9. SelfQAAdapter.run(ctx)     → self_qa (custom)
```

**Problemas del V2 existente:**
1. `KBAdapter` instancia `HomologationPipeline` internamente (dependencia directa)
2. `ParserAdapter` importa `parsear_excel` desde `app_validacion` (dependencia circular con UI)
3. `DIEAdapter` espera archivo en disco, no recibe stream desde UI
4. `DecisionAdapter` usa `decision_engine.py` (root), que es un módulo diferente a `decision/engine.py`
5. No hay soporte para Excel en pipeline_v2 (ParserAdapter sí lo maneja, bien)
6. El flujo no coincide con el orden ideal: SIE antes de DIE es cuestionable

---

## Conclusión del Análisis

El proyecto ya tiene **dos pipelines completos**:
- **V1** (`HomologationPipeline` en `pipeline/`): usado por app_validacion, funciona con Streamlit, tiene dependencia circular
- **V2** (`HomologationPipelineV2` en `orchestrator/`): usa DocumentContext, modular, pero tiene dependencias circulares y no está conectado a la UI

**Ninguno de los dos es "productivo".** V2 es la base correcta pero requiere:
1. Romper dependencia circular con app_validacion
2. Asegurar que todos los módulos reciban DocumentContext
3. Agregar soporte para entrada streaming (no solo archivo en disco)
4. Conectar UI a V2 en lugar de V1
