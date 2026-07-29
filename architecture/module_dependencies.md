# Matriz de dependencias entre módulos

## Convenciones

- `→` significa "depende de / recibe input de"
- `⇄` significa "dependencia bidireccional / colaboración"
- `produces` es el tipo de dato de salida principal

---

## IDR — Intelligent Document Router

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (inicial) |
| **Produce** | DocumentContext (enriquecido con `document_type`, `family`, `routing_path`) |
| **Descripción** | Examina el documento en INBOX, detecta tipo documental (balance, resultados, patrimonio) y familia (PYME, grande, sector público), y enruta al processing path correcto. |
| **Estado** | FUTURO (Sprint 22) |

---

## SIE — Structure Intelligence Engine

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `raw_lines`, `document_type`) |
| **Depende de** | TemplateRepository (consulta de templates conocidos) |
| **Produce** | DocumentContext (enriquecido con `structure`, `template_match`, `layout`) |
| **Descripción** | Analiza la estructura del documento: construye árbol jerárquico, detecta secciones, clasifica nivel de cada cuenta, mide similitud contra templates conocidos. |
| **Estado** | EXISTE como `structure_engine/` |

---

## Template Repository

| Campo | Valor |
|---|---|
| **Depende de** | SIE (recibe templates nuevos para almacenar) |
| **Depende de** | Sistema de archivos (JSON persistido) |
| **Produce** | Templates disponibles para matching |
| **Descripción** | Almacena, recupera y clasifica plantillas estructurales. Permite que SIE consulte templates existentes y registre nuevos. |
| **Estado** | EXISTE como `template_repository.py` dentro de `structure_engine/` |

---

## Parser

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `structure`, `template`, `layout`) |
| **Produce** | DocumentContext (enriquecido con `accounts: list[AccountBalance]`) |
| **Descripción** | Extrae cuentas y montos del documento usando el contexto estructural. Aplica el parser específico según el tipo documental (PDF, Excel, OCR). |
| **Estado** | EXISTE como `parsers/` |

---

## Knowledge Base CMCC

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `accounts: list[AccountBalance]`) |
| **Depende de** | Gold Standard (`gold_standard.db`) |
| **Produce** | DocumentContext (enriquecido con `knowledge: list[KnowledgeMatch]`) |
| **Descripción** | Homologa cada cuenta extraída contra el conocimiento canónico: busca el código y nombre canónico, asigna AccountType, resuelve sinónimos, aplica reglas de correspondencia. |
| **Estado** | EXISTE como `knowledge_base/` |

---

## BIV — Balance Integrity Validator

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `accounts`, `knowledge`) |
| **Produce** | DocumentContext (enriquecido con `validation: ValidationResult`) |
| **Descripción** | Valida la integridad contable: construye jerarquía, verifica subtotales, comprueba ecuación A=P+E, detecta cuentas faltantes, calcula puntajes de integridad. |
| **Estado** | EXISTE como `validation/` |

---

## Confidence Engine

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `accounts`, `knowledge`, `validation`) |
| **Produce** | DocumentContext (enriquecido con `confidence: ConfidenceResult`) |
| **Descripción** | Evalúa la confianza de cada cuenta homologada usando señales: fuzzy score, consensus entre clasificadores, cobertura en KB, validación contable. Produce confianza por cuenta y global. |
| **Estado** | FUTURO (Sprint 23) |

---

## Coverage Engine

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `accounts`, `knowledge`, `confidence`) |
| **Produce** | DocumentContext (enriquecido con `coverage: CoverageResult`) |
| **Descripción** | Mide qué proporción del balance está cubierta por la KB, qué cuentas quedaron sin homologar, qué secciones tienen baja cobertura. Genera recomendaciones de revisión. |
| **Estado** | FUTURO (Sprint 24) |

---

## Human Review Workspace

| Campo | Valor |
|---|---|
| **Depende de** | DocumentContext (con `coverage`, `confidence`, `validation`) |
| **Produce** | DocumentContext (enriquecido con `review: ReviewCandidate`) |
| **Produce** | Decisiones humanas persistidas en SQLite |
| **Descripción** | Presenta cuentas de baja confianza/cobertura para revisión humana. Almacena decisiones, permite búsqueda por similitud, exporta correcciones al Gold Standard. |
| **Estado** | EXISTE como `review_workspace/` |

---

## Dataset Manager

| Campo | Valor |
|---|---|
| **Depende de** | Sistema de archivos (directorios INBOX, TRAINING, HOLDOUT) |
| **Produce** | Manifiesto de datasets, ciclo de vida de documentos |
| **Descripción** | Gestiona el movimiento de documentos entre estados (INBOX → TRAINING → HOLDOUT → ARCHIVE), mantiene registro SQLite del ciclo de vida. |
| **Estado** | EXISTE como `dataset_manager.py` |

---

## Benchmark

| Campo | Valor |
|---|---|
| **Depende de** | Pipeline completo (todos los módulos anteriores) |
| **Depende de** | DatasetManager (para acceder a HOLDOUT) |
| **Produce** | Métricas de calidad, reportes de rendimiento |
| **Descripción** | Ejecuta el pipeline completo sobre el dataset HOLDOUT, mide precisión, cobertura, confianza y rendimiento. Genera reportes comparativos. |
| **Estado** | EXISTE como `benchmark/` |

---

## Matriz completa de dependencias

| Módulo | Depende de | Produce | Estado |
|---|---|---|---|
| IDR | — (entrada: archivo en INBOX) | DocumentContext (tipo, familia, ruta) | Futuro |
| SIE | IDR, TemplateRepository | DocumentContext (estructura, template) | Existente |
| TemplateRepository | SIE (escritura), SIE (lectura) | Templates persistidos | Existente |
| Parser | SIE, IDR | DocumentContext (cuentas) | Existente |
| Knowledge Base CMCC | Parser, GoldStandard | DocumentContext (knowledge) | Existente |
| BIV | KnowledgeBaseCMCC | DocumentContext (validation) | Existente |
| Confidence Engine | BIV | DocumentContext (confidence) | Futuro |
| Coverage Engine | ConfidenceEngine | DocumentContext (coverage) | Futuro |
| Human Review | CoverageEngine | DocumentContext (review), SQLite | Existente |
| Dataset Manager | Sistema de archivos | Manifiesto de datasets | Existente |
| Benchmark | Pipeline completo, DatasetManager | Métricas, reportes | Existente |

---

## Resumen visual de dependencias

```
IDR
  │
  ▼
SIE ◄──► TemplateRepository
  │
  ▼
Parser
  │
  ▼
KnowledgeBaseCMCC ◄── GoldStandard
  │
  ▼
BIV
  │
  ▼
Confidence Engine      ← FUTURO
  │
  ▼
Coverage Engine        ← FUTURO
  │
  ▼
HumanReviewWorkspace ──► SQLite
  │
  ▼
Resultado Final
```
