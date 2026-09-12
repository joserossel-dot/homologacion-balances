# Plan previo de poda de módulos

Fecha de corte: 2026-08-30. Fuente reproducible:
`python3 scripts/audit_module_usage.py --root .`.

## Alcance y criterio

Este análisis revisa los módulos marcados `orphan` por el grafo estático. No
es una autorización de borrado. Para cada módulo se contrastaron:

1. inbound estático desde código de ejecución;
2. inbound estático desde pruebas;
3. entrypoints Docker, Render, Poetry y guardias `__main__`;
4. referencias textuales en documentación y configuración;
5. imports dinámicos mediante `importlib`, `__import__`, `pkgutil` o registros de
   plugins;
6. responsabilidad declarada en docstring, símbolos públicos e imports internos.

No puedo verificar consumidores externos al repositorio. La ausencia de inbound
estático es evidencia negativa, pero no prueba que una API pública no sea usada
por una herramienta externa.

### Acciones

- **CONSERVAR**: fachada o marcador de un paquete con hijos vigentes, o ruta
  offline identificada;
- **DECISIÓN HUMANA**: no está conectada hoy, pero existe intención documental,
  datos asociados o una API pública con posible valor futuro;
- **ELIMINABLE**: reúne evidencia negativa múltiple: sin inbound runtime, sin
  inbound tests, sin entrypoint, sin referencia funcional en docs/config y sin
  registro dinámico encontrado. Aun así, requiere aprobación antes de borrar.

## Revisión por módulo

| Módulo | Función declarada | Import dinámico posible | Docs/config/entrypoint | Cobertura de pruebas | Riesgo | Acción recomendada |
|---|---|---|---|---|---|---|
| `config` | `__init__` vacío del paquete de configuración | No observado; import externo no verificable | Sus hijos contienen regex productivas y YAML | Sin import directo; hijos sí están cubiertos | Alto: retirar el marcador afecta semántica de paquete | **CONSERVAR** |
| `config.features` | Registro genérico y lectura/escritura de `features.yaml` | No observado | `config/features.yaml` existe; el plan universal exige una fachada tras feature flag | Sin import estático desde tests | Medio: podría reutilizarse para integrar Pipeline V2 | **DECISIÓN HUMANA** |
| `decision` | Fachada que reexporta `DecisionEngine` y modelos | No observado | `decision.engine` es consumido por el pipeline tras bandera | Sin import directo del `__init__`; hijos con pruebas | Alto: es fachada de hijos feature-gated vigentes | **CONSERVAR** |
| `gold_standard.exporter` | Exporta `GoldRecord` a CSV, JSON y JSONL | No observado; API pública podría usarse externamente | Sin entrypoint ni referencia funcional encontrada | Sin import estático desde tests | Medio: utilidad offline válida, aunque desconectada | **DECISIÓN HUMANA** |
| `knowledge_base` | Fachada de la base de conocimiento histórica | No observado como carga de módulo | `features.yaml` declara `knowledge_base`; comparte directorio con JSON usados por UI y extractores | Sin import estático desde tests | Alto: colisión entre código huérfano y datos productivos | **DECISIÓN HUMANA** |
| `knowledge_base.account` | Modelo `FinancialAccount` | No observado | Sólo clúster Python interno; datos del directorio sí tienen consumidores | Sin cobertura detectada | Medio: base del clúster histórico | **DECISIÓN HUMANA** |
| `knowledge_base.audit` | Auditoría y métricas de calidad de la KB | Usa `__import__('datetime')`, no descubrimiento de plugins | Genera reportes propios; no tiene entrypoint declarado | Sin cobertura detectada | Medio: herramienta offline no gobernada | **DECISIÓN HUMANA** |
| `knowledge_base.cmcc_builder` | Construye KB CMCC desde Gold | No observado | Referido por `cmcc_statistics`; `cmcc_knowledge.json` tiene consumidores separados | Sin cobertura detectada | Alto: podría regenerar un artefacto usado por clasificación | **DECISIÓN HUMANA** |
| `knowledge_base.cmcc_models` | Modelos de familia, código y variantes CMCC | No observado | Clúster builder/statistics | Sin cobertura detectada | Medio: contrato interno de generación CMCC | **DECISIÓN HUMANA** |
| `knowledge_base.cmcc_statistics` | Estadísticas y validación CMCC | No observado | Importa builder/modelos; sin entrypoint declarado | Sin cobertura detectada | Medio: herramienta de validación offline | **DECISIÓN HUMANA** |
| `knowledge_base.exporter` | Exportador del repositorio histórico | No observado | Reexportado por la fachada `knowledge_base` | Sin cobertura detectada | Medio: API pública del clúster | **DECISIÓN HUMANA** |
| `knowledge_base.loader` | Carga cuentas, relaciones, reglas y sinónimos | No observado | Reexportado por la fachada | Sin cobertura detectada | Medio: API pública del clúster | **DECISIÓN HUMANA** |
| `knowledge_base.relation` | Modelo y administrador de relaciones | No observado | Usado sólo dentro del clúster histórico | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.repository` | Repositorio en memoria del clúster histórico | No observado | Usado por loader/exporter/validator | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.rule` | Modelo y administrador de reglas | No observado | Usado sólo dentro del clúster histórico | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.synonym` | Modelo y administrador de sinónimos | No observado | Usado sólo dentro del clúster histórico | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.taxonomy` | Árbol taxonómico del clúster histórico | No observado | Usado por repository y fachada | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.validator` | Valida cuentas y repositorio histórico | No observado | Reexportado por la fachada | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `knowledge_base.version` | Versión del clúster histórico | No observado | Usado por fachada y exporter | Sin cobertura detectada | Bajo aislado, alto si se poda parcialmente | **DECISIÓN HUMANA** |
| `learning` | Fachada de `LearningEngine`, exact match y modelos | No observado | `learning.engine` es productivo | Sin import directo del `__init__`; hijos con pruebas | Alto: fachada de un paquete productivo | **CONSERVAR** |
| `learning.statistics` | Stub de estadísticas sin símbolos funcionales | No observado | Sin referencia funcional, configuración ni entrypoint | Sin cobertura detectada | Bajo: seis líneas recreadas sólo por compatibilidad histórica no ejercida | **ELIMINABLE** |
| `models.accounting_record` | Modelo canónico de fila con cuatro montos | No observado | Sin referencia nominal; el plan universal pide un contrato canónico más rico | Sin cobertura detectada | Alto: puede ser precursor de `RawLedgerDocument`, aunque hoy es insuficiente | **DECISIÓN HUMANA** |
| `orchestrator` | Fachada de `HomologationPipelineV2` | No observado | Pipeline V2 está priorizado en el plan universal | El hijo `pipeline_v2` tiene pruebas; la fachada no se importa directamente | Alto: ruta futura aprobada conceptualmente | **CONSERVAR** |
| `parsers` | Fachada de Parser Core 2.0 | No observado | Docstring lo declara prototipo; el plan universal requiere concurso de extractores | Sin cobertura detectada para esta fachada | Alto: arquitectura candidata de extracción | **DECISIÓN HUMANA** |
| `parsers.config` | Configuración de Parser Core 2.0 | No observado | Consumido dentro del clúster Parser Core 2.0 | Sin cobertura detectada | Alto dentro del clúster | **DECISIÓN HUMANA** |
| `parsers.excel_parser` | Adaptador Excel hacia `CuentaRaw` | No observado | Sin entrypoint; Excel es requisito explícito del plan universal | Sin cobertura detectada | Alto: capacidad futura relevante | **DECISIÓN HUMANA** |
| `parsers.factory` | Selecciona parser v1 o Parser Core 2.0 | No observado | Reexportado por `parsers`; alineado con concurso de estrategias | Sin cobertura detectada | Alto: posible punto de integración futura | **DECISIÓN HUMANA** |
| `parsers.format_detector` | Detecta código y separador de miles | No observado | Consumido por Parser Core 2.0 | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `parsers.hygiene` | Envuelve patrones de basura del parser vigente | No observado | Consumido por Parser Core 2.0 | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `parsers.integration` | Integración opcional analyzer + parser v1 | No observado | Reexportado por `parsers`; incluye ejemplo de uso, no entrypoint | Sin cobertura detectada | Medio: posible puente de migración | **DECISIÓN HUMANA** |
| `parsers.line_parser` | Convierte líneas a `RawAccount` y `CuentaRaw` | No observado | Consumido por Excel y Parser Core 2.0 | Sin cobertura detectada | Alto dentro del clúster | **DECISIÓN HUMANA** |
| `parsers.ocr_engine` | Interfaz OCR y Tesseract enchufable | No registro dinámico observado | Sin consumidor actual; OCR por región es requisito del plan universal | Sin cobertura detectada | Alto: coincide con una mejora planificada | **DECISIÓN HUMANA** |
| `parsers.orientation_detector` | Corrige orientación por coordenadas | No observado | Consumido por `parsers.analyzer`, fuera del entrypoint productivo | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `parsers.pdf_parser` | Orquestador Parser Core 2.0 | No observado | Creado por `parsers.factory`; prototipo declarado | Sin cobertura detectada | Alto: candidato futuro, no poda aislada | **DECISIÓN HUMANA** |
| `parsers.text_normalizer` | Higiene textual previa a análisis estructural | No observado | Consumido por `parsers.analyzer` | Sin cobertura detectada | Medio | **DECISIÓN HUMANA** |
| `pipeline` | `__init__` vacío del paquete operativo | No observado | Contiene el pipeline productivo | Sin import directo; hijos ampliamente probados | Alto: marcador de paquete productivo | **CONSERVAR** |
| `pipeline.new_pipeline` | Adaptador simple ParserPDF -> AccountBalance | No observado | Sin entrypoint, configuración o mención funcional; existen pipeline operativo y V2 | Sin cobertura detectada | Bajo: duplicación sin consumidor | **ELIMINABLE** |
| `review` | Fachada de revisión CMCC y paquete Excel histórico | No observado | Reexporta módulos activos y offline | Sin import directo; hijos CMCC sí tienen pruebas | Alto: fachada mixta | **CONSERVAR** |
| `review.excel_formatter` | Formatea hojas del paquete Excel de revisión | No observado | Consumido por `review_package_builder` | Sin cobertura detectada | Medio: parte de herramienta offline coherente | **CONSERVAR** |
| `review.review_metrics` | Prioriza cuentas y arma dashboard de revisión | No observado | Consumido por `review_package_builder` | Sin cobertura detectada | Medio: parte de herramienta offline coherente | **CONSERVAR** |
| `review.review_models` | Modelos del paquete de revisión | No observado | Consumido por formatter, metrics y builder | Sin cobertura detectada | Medio: contrato de herramienta offline | **CONSERVAR** |
| `review.review_package_builder` | Genera workbook de revisión desde datos shadow | No observado | Consumido por `review/run_review_package.py`, que tiene guardia `__main__` | Sin cobertura detectada | Medio: alcanzable desde entrypoint offline | **CONSERVAR** |
| `semantic` | Fachada de matcher, modelos, normalizador y scorer | No observado | Hijos importados por el pipeline tras bandera semántica | Sin import directo; hijos tienen pruebas | Alto: fachada feature-gated | **CONSERVAR** |
| `semantic.semantic_catalog` | Catálogo de tipos semánticos e IFRS | No observado | Sin referencia funcional; `SemanticEngine` usa reglas y no este catálogo | Sin cobertura detectada | Bajo: implementación aislada y duplicada conceptualmente | **ELIMINABLE** |
| `src.api` | `__init__` vacío de la API heredada retirada | No observado | Sólo referencia histórica en documentación; no entrypoint | Sin cobertura salvo prueba que confirma retiro de la API | Bajo: paquete vacío sin consumidores | **ELIMINABLE** |
| `validation` | Fachada de validadores y modelos | No observado | Hijos son parte del flujo productivo y certificación | Sin import directo; hijos ampliamente probados | Alto: fachada de paquete productivo | **CONSERVAR** |

## Lote seguro potencial, no ejecutado

Revisión del candidato del 2026-09-12: `account_name_normalizer` y
`special_account_rules` se conservan desconectados de producción. Tienen pruebas
directas de aislamiento de configuración, conservación de calificadores y
conflictos de candidatos en `tests/test_experimental_account_knowledge.py`.
Por eso ya no figuran como huérfanos en el inventario que incluye imports de
pruebas. Ese cambio no significa integración productiva ni certificación Gold.
Sus coincidencias son hipótesis, no clasificaciones aprobadas. No se añadieron
imports productivos artificiales para ocultar su estado experimental.
Antes de integrarlos se requiere resolver naturaleza y plazo de préstamos con
socios/relacionadas, distinguir patentes tributarias de intangibles y alinear
impuestos diferidos con el catálogo vigente. No corresponde habilitar todas sus
reglas por similitud de texto ni elevar sus puntajes a confianza productiva.

El único lote que reúne evidencia negativa múltiple sin arrastrar clústeres
conectados es:

1. `learning/statistics.py`;
2. `pipeline/new_pipeline.py`;
3. `semantic/semantic_catalog.py`;
4. `src/api/__init__.py`.

Evidencia común: cero inbound runtime, cero inbound desde pruebas, cero
entrypoints, ningún registro dinámico encontrado y ninguna configuración que los
cargue. Además:

- `learning.statistics` declara ser un stub de compatibilidad y no expone
  funcionalidad;
- `pipeline.new_pipeline` duplica parcialmente dos rutas existentes y no está en
  la secuencia del plan universal;
- `semantic.semantic_catalog` no es consumido por `SemanticEngine`;
- `src.api` quedó vacío tras retirar la API insegura.

Antes de borrar, la revisión humana debe confirmar que no existen scripts o
consumidores fuera del repositorio. La poda debe ser un commit aislado, ejecutar
la suite completa y comparar el JSON antes/después. No se recomienda incluir
`config.features`, `models.accounting_record`, `gold_standard.exporter` ni ningún
archivo de los clústeres `knowledge_base` o Parser Core 2.0 en ese lote.

## Decisiones humanas requeridas

1. Confirmar si Parser Core 2.0 será integrado o archivado como conjunto.
2. Confirmar si el código Python de `knowledge_base` regenera artefactos CMCC en
   algún proceso externo; los JSON del directorio no deben podarse.
3. Definir si `models.accounting_record` se migra al contrato universal o se
   sustituye por el nuevo modelo preservando compatibilidad.
4. Determinar si el paquete Excel histórico de `review` sigue siendo una
   herramienta operacional offline.
5. Confirmar consumidores externos del lote seguro potencial.

## Revalidación

```bash
python3 scripts/audit_module_usage.py --root . --pretty \
  --output module-usage-before-pruning.json
python3 -m pytest -q
```

El JSON posterior a una poda aprobada debe conservar el entrypoint
`app_validacion`, mantener cero bypass TLS y no convertir módulos productivos en
huérfanos nuevos.
