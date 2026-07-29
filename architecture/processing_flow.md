# Flujo de procesamiento completo

## Diagrama paso a paso

```
datasets/INBOX/
      │
      │ [1] Llega un PDF/Excel a INBOX
      ▼
┌──────────────────────────────────────────────────────┐
│  1. IDR — Intelligent Document Router                │
│                                                      │
│  ● Identifica tipo documental (balance/resultados)   │
│  ● Detecta formato (PDF/Excel/OCR)                   │
│  ● Clasifica familia (PYME/GRANDE/SP)                │
│  ● Crea DocumentContext inicial                      │
│  ● Asigna document_id UUID                           │
│  ● Mueve archivo a PROCESSING/                       │
│                                                      │
│  Output: DocumentContext (document_type, family,     │
│          source_format, document_id)                 │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  2. SIE — Structure Intelligence Engine              │
│                                                      │
│  ● Extrae raw_lines del documento                    │
│  ● Normaliza texto                                   │
│  ● Detecta layout de columnas                        │
│  ● Construye StructuralTree (jerarquía de cuentas)   │
│  ● Detecta secciones y niveles                       │
│  ● Calcula StructuralSignature                       │
│                                                      │
│  Output: DocumentContext (structure, layout,         │
│          sections, pages, structural_signature)      │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  3. Template Matching (SIE + TemplateRepository)     │
│                                                      │
│  ● Busca templates similares en TemplateRepository   │
│  ● Si hay match ≥ threshold: asigna template         │
│  ● Si no hay match: crea nuevo template candidate    │
│  ● Clasifica familia por template si IDR no lo hizo  │
│                                                      │
│  Output: DocumentContext (template, template_match,  │
│          template_id, family)                        │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  4. Parser — Extracción de cuentas                   │
│                                                      │
│  ● Usa layout y template para guiar el parseo        │
│  ● Parsea cada línea → AccountBalance               │
│  ● Detecta niveles, subtotales, totales              │
│  ● Resuelve tipo de cuenta (nature)                  │
│  ● Aplica higiene (filtra líneas basura)             │
│  ● Calcula métricas de parseo                        │
│                                                      │
│  Output: DocumentContext (accounts: list[            │
│          AccountBalance], parse_metrics,             │
│          parser_version)                             │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  5. Knowledge Base CMCC — Homologación               │
│                                                      │
│  ● Para cada AccountBalance:                         │
│    - Busca código canónico en CMCC                   │
│    - Busca por nombre (exacto, fuzzy, sinónimos)     │
│    - Resuelve accountType                            │
│    - Aplica reglas de negocio                        │
│  ● Clasifica cuentas COBERTURA vs TARGET             │
│  ● Genera KnowledgeMatch por cuenta                  │
│                                                      │
│  Output: DocumentContext (knowledge: list[           │
│          KnowledgeMatch], kb_version,                │
│          homologation_stats)                         │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  6. BIV — Balance Integrity Validator                │
│                                                      │
│  ● Construye HierarchyTree desde accounts            │
│  ● Valida subtotales                                 │
│  ● Valida ecuación A = P + E                         │
│  ● Valida ecuación A = P + PN + R                    │
│  ● Detecta cuentas faltantes                         │
│  ● Calcula puntajes de integridad                    │
│    (extracción, clasificación, jerarquía)            │
│  ● Genera reporte de validación                      │
│                                                      │
│  Output: DocumentContext (validation:               │
│          ValidationResult)                           │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  7. Confidence Engine — Evaluación de confianza      │
│                                                      │
│  ● Por cada cuenta homologada:                       │
│    - Señal fuzzy: score del matching                 │
│    - Señal consensus: acuerdo entre clasificadores   │
│    - Señal validation: pasa validación contable?     │
│    - Señal kb_coverage: presente en KB?              │
│  ● Ponderación de señales → confianza por cuenta     │
│  ● Agregación → confianza global del documento       │
│  ● Threshold → marca cuentas que necesitan review    │
│                                                      │
│  Output: DocumentContext (confidence:               │
│          ConfidenceResult)                           │
│                                                      │
│  ⚠ FUTURO (Sprint 23) — No implementado aún         │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  8. Coverage Engine — Medición de cobertura          │
│                                                      │
│  ● Porcentaje de cuentas cubiertas por KB            │
│  ● Cuentas no resueltas → lista                      │
│  ● Cobertura por sección del balance                 │
│  ● Genera recomendaciones (add_to_kb, review,        │
│    auto_approve)                                     │
│  ● Prioriza cuentas críticas sin cobertura           │
│                                                      │
│  Output: DocumentContext (coverage: CoverageResult)  │
│                                                      │
│  ⚠ FUTURO (Sprint 24) — No implementado aún         │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  9. Human Review Workspace                           │
│                                                      │
│  ● Filtra cuentas con confianza < threshold           │
│  ● Agrupa por prioridad (cobertura + confianza)      │
│  ● Presenta candidatos a revisión                    │
│  ● Humano decide: aprueba, rechaza, edita, salta     │
│  ● Persiste decisiones en SQLite                     │
│  ● Opcional: exporta correcciones a Gold Standard    │
│                                                      │
│  Output: DocumentContext actualizado + SQLite        │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│  10. Exportación — Resultado Final                   │
│                                                      │
│  ● Genera reporte estructurado (JSON/CSV/Excel)      │
│  ● Incluye: cuentas homologadas, metadatos,          │
│    validación, confianza, cobertura                  │
│  ● Mueve archivo a COMPLETED/ o ARCHIVE/             │
│  ● Si aplica, agrega a TRAINING o HOLDOUT            │
│                                                      │
│  Output: Archivo exportado + Dataset actualizado     │
└──────────────────────────────────────────────────────┘
```


## Flujo alternativo: revisión diferida

Cuando no hay Confidence Engine ni Coverage Engine (situación actual),
el flujo simplificado es:

```
INBOX → IDR → SIE → TemplateRepo → Parser → KB → BIV → Review → Export
                                                          │
                                                    (solo UNKNOWNs
                                                     del pipeline actual)
```


## Flujo alternativo: procesamiento batch

Para benchmarks y validación batch:

```
DatasetManager.scan(HOLDOUT)
  │
  ├── doc1.pdf → Pipeline completo → Export resultados
  ├── doc2.pdf → Pipeline completo → Export resultados
  └── ...
       │
       ▼
BenchmarkRunner → Métricas agregadas → Reporte
```


## Flujo alternativo: auto-aprobación

Cuando `confidence.global_score > threshold_auto` y
`coverage.kb_coverage_pct > threshold_coverage`:

```
Pipeline → Confidence → Coverage → Export
                                      │
                                (salta ReviewWorkspace)
```


## Estados de archivo durante el flujo

```
INBOX/         → Archivo original sin procesar
PROCESSING/    → Archivo siendo procesado (IDR lo mueve aquí)
COMPLETED/     → Procesamiento exitoso
REVIEW/        → Requiere revisión humana
ARCHIVE/       → Procesado y archivado
ERROR/         → Error no recuperable
```


## Diagrama de decisión de revisión

```
                        ┌─ threshold_auto
                        ▼
               ┌────────────────┐
               │ confidence >=  │
               │ threshold_auto │── Sí ──→ Export directo
               └────────┬───────┘
                        │ No
                        ▼
               ┌────────────────┐
               │ confidence >=  │
               │ threshold_rev  │── Sí ──→ ReviewWorkspace
               └────────┬───────┘
                        │ No
                        ▼
               ┌──────────────────────┐
               │ ReviewWorkspace       │
               │ (prioridad alta)      │
               └──────────────────────┘
```
