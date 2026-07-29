# Arquitectura de homologacion-balances

## Visión

Plataforma unificada de procesamiento de balances que transforma documentos
financieros (PDF/Excel) en datos estructurados y homologados. La arquitectura
está diseñada para incorporar nuevos parsers, nuevos tipos documentales y
nuevos motores de inteligencia sin requerir reorganizaciones estructurales.

Cada módulo es autónomo, reemplazable y se comunica mediante contratos
explícitos. El estado compartido vive en un único objeto `DocumentContext`
que atraviesa toda la canalización.

---

## Principios de diseño

| Principio | Aplicación |
|---|---|
| **Single Responsibility** | Cada módulo resuelve exactamente un problema. Si hay más de una razón para cambiar un módulo, se divide. |
| **Dependency Inversion** | Los módulos de alto nivel dependen de interfaces abstractas, no de implementaciones concretas. |
| **Open / Closed** | Los módulos están abiertos a extensión (nuevos parsers, nuevos motores) pero cerrados a modificación directa. |
| **Context-Driven** | `DocumentContext` es el contrato único que atraviesa todo el pipeline. Ningún módulo necesita conocer la existencia de los demás. |
| **Fail Fast con Resilience** | Errores se capturan a nivel de campo en el contexto. Un fallo en validación no impide que confianza/cobertura se calculen sobre lo disponible. |
| **Idempotencia** | Procesar el mismo documento con el mismo contexto base produce el mismo resultado. |
| **Replaceability** | Cualquier módulo puede ser reemplazado por otra implementación que cumpla su interfaz, sin modificar el resto del sistema. |
| **Separation by Change Rate** | Los módulos se organizan por su frecuencia de cambio esperada: infraestructura (baja), dominio (media), aplicación (alta). |

---

## Separación por capas

```
┌─────────────────────────────────────────────────┐
│               PRESENTATION LAYER                 │
│  Streamlit UI  │  FastAPI  │  CLI / Scripts     │
├─────────────────────────────────────────────────┤
│               APPLICATION LAYER                  │
│  IDR  │  Confidence  │  Coverage  │  Pipeline   │
├─────────────────────────────────────────────────┤
│                DOMAIN LAYER                      │
│  SIE  │  Parser  │  KB CMCC  │  BIV             │
├─────────────────────────────────────────────────┤
│             INFRASTRUCTURE LAYER                 │
│  DocumentContext  │  TemplateRepo  │  ReviewWS  │
│  DatasetManager   │  Benchmark     │  Export    │
└─────────────────────────────────────────────────┘
```

### Presentation Layer

Interactúa con el usuario final. Muestra resultados, recibe correcciones,
visualiza métricas. No contiene lógica de negocio.

**Responsabilidades:**
- Renderizar dashboards y reportes
- Recibir documentos (upload)
- Exponer APIs REST
- Ejecutar scripts de análisis

**Componentes existentes:**
- `app_validacion.py` — Streamlit monolith (candidato a refactor)
- `review_ui/` — Interfaz de revisión humana
- `src/api/main.py` — API REST FastAPI
- `scripts/` — Utilidades CLI

### Application Layer

Orquesta el flujo de procesamiento. Enruta documentos, mide confianza y
cobertura. Es la capa más volátil: los casos de uso cambian con más
frecuencia que la lógica de dominio.

**Responsabilidades:**
- Enrutar documentos según tipo/familia (IDR)
- Orquestar secuencia de procesamiento
- Calcular confianza y cobertura
- Coordinar revisión humana

**Componentes actuales:**
- `pipeline/` — Orquestación (HomologationPipeline, NewPipeline)
- `decision/`, `decision_v2/` — Motores de decisión

**Componentes futuros:**
- IDR (Sprint 22)
- Confidence Engine (Sprint 23)
- Coverage Engine (Sprint 24)

### Domain Layer

Contiene la lógica de negocio pura. Cada módulo de dominio resuelve un
problema específico del dominio financiero-contable sin conocer el pipeline
que lo invoca.

**Responsabilidades:**
- Extraer texto y tablas de documentos (Parser)
- Identificar estructura, familias y plantillas (SIE)
- Homologar cuentas contra conocimiento canónico (KB CMCC)
- Validar integridad contable: ecuaciones, jerarquías, subtotales (BIV)

**Componentes existentes:**
- `parsers/` — Parser Core 2.0
- `structure_engine/` — SIE (Structure Intelligence Engine)
- `knowledge_base/` — Knowledge Base CMCC
- `validation/` — BIV (Balance Integrity Validator)
- `semantic/` — Matching semántico
- `learning/` — Aprendizaje desde Gold Standard
- `models/` — Modelos de dominio

### Infrastructure Layer

Provee servicios transversales: persistencia, contextos compartidos,
gestión de datos, exportación. Los módulos de infraestructura rara vez
cambian.

**Responsabilidades:**
- Definir y transportar DocumentContext
- Persistir templates, revisiones, resultados
- Gestionar datasets (INBOX, TRAINING, HOLDOUT)
- Ejecutar benchmarks y métricas

**Componentes existentes:**
- `review_workspace/` — Base de datos SQLite de revisión
- `dataset_manager.py` — Ciclo de vida de datasets
- `benchmark/` — Runner de benchmarks
- `adapters/` — Adaptadores de datos
- `evidence/`, `explainability/` — Trazabilidad

---

## Mapa de módulos vs capas

| Módulo | Capa | Estado |
|---|---|---|
| IDR (Document Router) | Application | Futuro (Sprint 22) |
| SIE (Structure Intelligence) | Domain | Existe como `structure_engine/` |
| Template Repository | Infrastructure | Existe como `template_repository.py` |
| Parser | Domain | Existe como `parsers/` |
| Knowledge Base CMCC | Domain | Existe como `knowledge_base/` |
| BIV (Balance Integrity Validator) | Domain | Existe como `validation/` |
| Confidence Engine | Application | Futuro (Sprint 23) |
| Coverage Engine | Application | Futuro (Sprint 24) |
| Human Review Workspace | Infrastructure | Existe como `review_workspace/` |
| Dataset Manager | Infrastructure | Existe como `dataset_manager.py` |
| Benchmark | Infrastructure | Existe como `benchmark/` |

---

## Technical Debt

### Duplicaciones

| Problema | Localización | Impacto | Recomendación |
|---|---|---|---|
| Patrones de totales/subtotales/headers duplicados | `validation/hierarchy.py`, `structure_engine/structure_detector.py`, `review_workspace/export_unknowns.py`, `review_workspace/pre_review_cleaner.py` | Alto | Unificar en un módulo `patterns/` compartido |
| Dos motores de decisión | `decision/` (v1), `decision_v2/` (v2) | Medio | Deprecar v1, migrar a v2 |
| Dos pipelines | `pipeline/homologation_pipeline.py`, `pipeline/new_pipeline.py` | Medio | Unificar en un solo pipeline orquestado por IDR |
| Dos dataset managers | `dataset_manager.py` (raíz), `validation/dataset_manager.py` | Bajo | Unificar en `dataset_manager/` como paquete |
| Dos sistemas de UI | `app_validacion.py` (Streamlit), `src/api/main.py` (FastAPI) | Bajo | Mantener separación por propósito (interactivo vs API) |

### Dependencias innecesarias

| Problema | Localización | Impacto | Recomendación |
|---|---|---|---|
| `parsers/*` importa directamente de `parser_universal.py` | Todos los archivos de `parsers/` | Alto | Completar la migración: eliminar dependencia del monolito, que `parsers/` sea el verdadero parser |
| `validation/runner.py` importa `pipeline.homologation_pipeline` | `validation/runner.py` | Medio | Invertir dependencia: que el pipeline use validación, no al revés |
| `app_validacion.py` importa de 11+ módulos | `app_validacion.py` | Alto | Refactorizar usando inyección de dependencias |

### Desacoplamientos necesarios

| Situación | Acción recomendada |
|---|---|
| `HomologationPipeline.process()` tiene 634 líneas | Extraer cada fase a un step independiente |
| La KB canónica (`knowledge_base/`) no se usa en el pipeline | Integrar `knowledge_base.Repository` como fuente de verdad |
| `parser_universal.py` es importado por 10+ módulos | Crear una `ParserInterface` abstracta y migrar todos los consumidores |
| `app_validacion.py` contiene lógica de negocio mezclada con UI | Separar en controladores + vistas |

### Oportunidades de simplificación

| Área | Propuesta |
|---|---|
| Clasificación de cuentas (5 mecanismos) | Unificar en un solo `ClassificationEngine` con estrategias plugables |
| Pipeline dual (homologation + new) | Unificar en `DocumentPipeline` parametrizable por tipo documental |
| Detección de estructura repetida en 4 módulos | Centralizar en `structure_engine/` y que los demás consuman desde allí |
