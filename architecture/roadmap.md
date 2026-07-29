# Roadmap — Próximos 6 sprints

## Resumen de sprints

| Sprint | Nombre | Entrega |
|---|---|---|
| 22 | Intelligent Document Router | IDR operational |
| 23 | Confidence Engine | Sistema de confianza por cuenta y global |
| 24 | Coverage Engine | Sistema de cobertura contra KB |
| 25 | Self QA | Auto-validación del pipeline completo |
| 26 | Production Pipeline | Pipeline listo para producción |

---

## Sprint 22 — Intelligent Document Router

**Objetivo:** Construir el primer módulo del pipeline lógico: el enrutador
inteligente de documentos.

### Entregables

1. **IDR Interface** — Implementar el Protocol definido en `interfaces.md`
2. **Type Detector** — Detectar si un documento es balance, resultados, patrimonio, etc.
   - Heurísticas: palabras clave, estructura de secciones, proporción de cuentas
3. **Family Classifier** — Clasificar familia: PYME, GRANDE, SECTOR_PUBLICO
   - Basado en: código de cuentas, cantidad de cuentas, tipo de entidad
4. **Format Detector** — Detectar fuente: PDF texto, PDF escaneado, Excel, CSV
5. **DocumentContext Factory** — Crear `DocumentContext` inicial con:
   - `document_id` (UUID)
   - `source_file`, `filename`, `file_hash`, `file_size`
   - `document_type`, `family`, `source_format`
6. **Pipeline Integration** — IDR como primer paso del pipeline
7. **Tests** — Cobertura ≥ 90% en detección de tipo y familia

### No incluye
- SIE (ya existe en `structure_engine/`)
- Confidence Engine (Sprint 23)

### Dependencias
- `structure_engine/` (existente) — IDR puede llamar a family_detector
- `DocumentContext` (definido en este diseño)

---

## Sprint 23 — Confidence Engine

**Objetivo:** Implementar el motor de confianza que evalúa qué tan seguros
estamos de cada homologación.

### Entregables

1. **ConfidenceEngine Interface** — Implementar Protocol
2. **Signal Sources**:
   - `FuzzySignal`: score del matching fuzzy (0.0-1.0)
   - `ConsensusSignal`: acuerdo entre clasificadores (KB, semántico, código, reglas)
   - `ValidationSignal`: si la cuenta pasa validación contable
   - `KBCoverageSignal`: si la cuenta existe en la KB
3. **Weighted Aggregator** — Combinar señales con pesos configurables
4. **Per-Account Confidence** — `AccountConfidence` con score + señales
5. **Global Confidence** — Score agregado del documento completo
6. **Threshold Engine** — Configurar thresholds: `auto_approve`, `require_review`, `critical`
7. **Integration Tests** — Validar contra gold_standard.db

### No incluye
- Coverage Engine (Sprint 24)
- IDR (Sprint 22)

### Dependencias
- `knowledge_base/` — para KB coverage signal
- `validation/` — para validation signal
- `DocumentContext.knowledge` y `DocumentContext.validation`

---

## Sprint 24 — Coverage Engine

**Objetivo:** Medir qué proporción del balance está cubierta por la Knowledge
Base y generar recomendaciones.

### Entregables

1. **CoverageEngine Interface** — Implementar Protocol
2. **KBCoverage Calculator**:
   - `kb_coverage_pct`: porcentaje de cuentas homologadas vs total
   - `missing_codes`: códigos no encontrados en KB
   - `unresolved_accounts`: cuentas sin match canónico
3. **Section Coverage** — Cobertura desglosada por sección (ACTIVO, PASIVO, etc.)
4. **Recommendation Generator** — Recomendaciones por cuenta:
   - `auto_approve`: confianza alta + cobertura alta
   - `review`: necesita revisión humana
   - `add_to_kb`: candidata para agregar a la KB
5. **Prioritization** — Ordenar recomendaciones por criticidad
6. **Integration Tests** — Validar contra gold_standard.db

### No incluye
- Self QA (Sprint 25)
- Mejoras a IDR

### Dependencias
- `knowledge_base/` — para determinar cobertura
- `ConfidenceEngine` (Sprint 23) — para priorizar recomendaciones

---

## Sprint 25 — Self QA

**Objetivo:** El pipeline se auto-valida. Detectar regresiones, medir calidad
y generar reportes automáticos.

### Entregables

1. **Regression Detection** — Comparar resultados actuales vs gold_standard
2. **Quality Metrics Dashboard** — Precisión, cobertura, confianza promedio
3. **Benchmark Automation** — Ejecutar benchmark automático contra HOLDOUT
4. **Drift Monitoring** — Detectar cambios en:
   - Distribución de tipos documentales
   - Tasa de UNKNOWNs
   - Confianza promedio
   - Tiempo de procesamiento
5. **Alert System** — Notificar cuando métricas caen bajo threshold
6. **Shadow Mode** — Modo silencioso que registra resultados sin afectar producción

### No incluye
- Production pipeline (Sprint 26)
- Mejoras a motores existentes

### Dependencias
- `benchmark/` (existente)
- `ConfidenceEngine` (Sprint 23)
- `CoverageEngine` (Sprint 24)
- `gold_standard.db`

---

## Sprint 26 — Production Pipeline

**Objetivo:** El pipeline completo está listo para ejecución en producción
con monitoreo, recovery y logging.

### Entregables

1. **Pipeline Orchestrator** — Orquestador que ejecuta los pasos en orden:
   ```
   IDR → SIE → TemplateRepo → Parser → KB → BIV → Confidence → Coverage → Review → Export
   ```
2. **Error Recovery** — Recomendación automática ante errores:
   - Error en Parser → continuar con datos parciales
   - Error en KB → continuar sin homologación
   - Error crítico → detener, mover a ERROR/
3. **Progress Tracking** — Reportar progreso en tiempo real
4. **Structured Logging** — Logs JSON con contexto completo
5. **Metrics Export** — Exportar métricas a sistema externo (Prometheus, etc.)
6. **Graceful Shutdown** — Completar documento en curso antes de detenerse
7. **CLI Final** — Interfaz CLI completa:
   ```bash
   python -m homologacion pipeline run documento.pdf
   python -m homologacion pipeline batch datasets/INBOX/
   python -m homologacion pipeline status <document_id>
   ```

### Dependencias
- Todos los sprints anteriores (22-25)
- Todos los módulos existentes

---

## Prioridades para los próximos 6 sprints

| Prioridad | Sprint | Razón |
|---|---|---|
| 🔴 Crítica | 22 — IDR | Sin IDR no hay pipeline lógico |
| 🔴 Crítica | 23 — Confidence | Sin confianza no podemos decidir qué revisar |
| 🟡 Alta | 24 — Coverage | Sin cobertura no sabemos qué falta |
| 🟡 Alta | 25 — Self QA | Sin auto-validación no hay calidad garantizada |
| 🟢 Media | 26 — Production | Depende de los 4 sprints anteriores |

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| IDR muy simple + heurístico | Media | Alto | Diseñar IDR con plug-in de clasificadores intercambiables |
| Confidence sobreingenierizado | Baja | Medio | Empezar con 3 señales simples, iterar |
| Coverage duplica lógica de KB | Media | Medio | Coverage solo lee KB, no la modifica |
| Self QA sin data suficiente | Alta | Medio | Usar HOLDOUT existente desde día 1 |
| Pipeline production sin tests | Media | Alto | Cada sprint entrega tests; Sprint 25 valida |
