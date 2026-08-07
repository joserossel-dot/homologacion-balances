# PROJECT_STATUS.md — Estado del Sistema de Homologación de Balances

Estado consolidado del sistema, componentes, benchmark, roadmap y deuda técnica.
**Última actualización:** 2026-08-05.

---

## 1. Estado general

El sistema está en **modo shadow / benchmark**. No emite decisiones CMCC en producción
(`ENABLE_CMCC = False`, `ENABLE_CMCC_PRODUCTION = False`, `ENABLE_CMCC_SHADOW = True`).

| Aspecto | Estado |
|---|---|
| Benchmark oficial | 2660/2662 (base M5, **99.92%**) — congelada |
| Runbenchmark HOLDOUT | 2.692 cuentas · 1.251 homologadas (48.77%) · 1.030 unknown |
| Certificación (2026-07-09) | 100% accuracy en cuentas cotejadas (103/103, κ = 1.0) |
| Auditoría RC1 (2026-07-29) | "No listo para piloto todavía" |
| Tests | 734 tests pasando (Sprint 26.1) |
| Backend | `2.0.0-rc1` |
| Modo de operación | Shadow / benchmark (CMCC desactivado en producción) |
| Errores del último cambio (P6) | 0 regresiones · gold_standard.db byte-idéntica |

**Ruta de la arquitectura:** doble vía V1 (legado, en uso por UI) + V2 (nuevo, backend). El
sistema está consolidando el conocimiento vía `RuntimeManager` sin tocar la base del benchmark.

---

## 2. Componentes implementados

| Componente | Estado |
|---|---|
| `gold_standard/runtime_manager.py` (RuntimeManager) | ✅ Implementado (P3) |
| Columna `activa` + depuración (96 activos / 11 inactivos) | ✅ Implementado (P6) |
| Runtime Observability | ✅ Implementado (P5.5) |
| Learning loop (runtime → revisión → promoción) | ✅ Implementado (P5) |
| Pipeline V1 (HomologationPipeline) | ✅ En uso (UI) |
| Pipeline V2 (HomologationPipelineV2, 9 adaptadores) | ✅ Activo (backend) |
| DIE — Document Intelligence Engine | ✅ Activo (V2, ~7.7k líneas) |
| SemanticMatcher (tiers 1-6) | ✅ En uso (V1) |
| Learning Engine (learning_exact / learning_fuzzy) | ✅ En uso (shadow) |
| Classification Engine CMCC | ✅ En uso (shadow) |
| Decision Engine V2 documental | ✅ Activo en V2 |
| Review Pipeline (revisión humana) | ✅ En uso |
| Gold Standard / Catálogo CMCC | ✅ En uso |
| UI Streamlit | ✅ En uso |
| API FastAPI (health, procesar) | ✅ En uso |

---

## 4. Componentes pendientes / no integrados

| Componente | Estado | Nota |
|---|---|---|
| Decision Engine V1 (`decision/`) | OFF | Flag `ENABLE_DECISION_ENGINE=False` |
| CMCC en producción | Pendiente | Rollout Phase 1-4 sin iniciar |
| ParserCore2 | Parcial | `ParserPDF` legacy es el que corre |
| Motor Top-N (`classification_engine/`) | No integrado | Sprint 39 |
| Decision benchmark (`decision_v2/`) | No integrado | Bug TB-3 conocido |
| `split_ac01` | No confiable | 11 tests fallan (C-4) |

---

## 3. Benchmark

### Benchmark oficial (base congelada)

| Ítem | Valor |
|---|---|
| Identificador | 2660/2662 (base M5) |
| Precisión | 99.92% |
| Estado | **Congelada** — solo lectura desde el runtime |
| Registrado | `gold_standard/promotion.py:12`, `app_validacion.py:1951` |

### Benchmark HOLDOUT (2026-07-26, 20 archivos)

| Métrica | Valor |
|---|---|
| Cuentas detectadas | 2.692 |
| Homologadas | 1.251 (48.77%) |
| Unknown | 1.030 |
| Learning hits | 101 |
| Precisión extracción ≈ | 16.19% |
| Confianza global ≈ | 0.1611 |

### Certificación oficial (2026-07-09)

- HOLDOUT: 20 documentos, 2.692 cuentas parseadas, 1.083 clasificadas.
- Gold Standard cotejado: **103 cuentas** (89 directas + 14 vía fuzzy).
- **Accuracy 100%**, Macro F1 1.0, Micro F1 1.0, Cohen's Kappa 1.0.
- > Nota: 100% solo en las cotejables; cobertura global continúa baja.

---

## 5. Cobertura y causa raíz del "unknown"

**Población de producción (URCA, 2026-07-10):** 10.672 cuentas en 185 documentos.

| Métrica | Valor |
|---|---|
| Clasificadas | 1.952 (18.3%) |
| No clasificadas | 8.720 |

**Causas raíz del no-clasificado:**

| Causa | Cuentas | % |
|---|---|---|
| RC05_DICTIONARY (no está en diccionario) | 5.134 | 58.9% |
| RC06_CMCC (no mapeable al catálogo) | 2.637 | 30.2% |
| RC02_OCR (texto corrupto) | 473 | 5.4% |
| RC01_LAYOUT (layout) | 292 | 3.3% |
| RC04_NORMALIZATION (normalización) | 184 | 2.1% |

**Simulación:** eliminar RC05+RC06 → cobertura **91.1%**; +RC03 → **95.5%**. El mayor
impacto está en completar diccionario y catálogo CMCC.

---

## 6. Learning Loop

```
runtime_gold (conocimiento en evolución)
      │  search_runtime (filtra act=1)      ✦ constante: benchmark lee gold, no runtime
      ▼
   clasificación ─► shadow ─► revisión humana (review/)
      │                                    │
      └── así evidencia ─────────► promoción auditable (promotion_history)
                                     ▼
                              actualización del conocimiento + metadatos
```

- La base del benchmark (2660/2662) **nunca se escribe desde el runtime**; el conocimiento nuevo
  evoluciona en `runtime_gold`.
- Cada promoción/rollback queda auditada en `promotion_history` (quién, cuándo, qué, de dónde).

---

## 7. Roadmap

### 7.1 Sprints (arquitectura objetivo)

| Sprint | Nombre | Entrega |
|---|---|---|
| 22 | Intelligent Document Router (IDR) | IDR operational |
| 23 | Confidence Engine | Confianza por cuenta y global |
| 24 | Coverage Engine | Cobertura contra KB |
| 25 | Self QA | Auto-validación del pipeline |
| 26 | Production Pipeline | Pipeline listo para producción |

### 7.2 Rollout CMCC (4 fases)

| Fase | Sprint | Objetivo | Estado |
|---|---|---|---|
| Phase 0 | 26.1 | Flags + métricas + tests | ✅ **COMPLETA** (734 tests) |
| Phase 1 | 2 | Shadow validation en UNKNOWN | Pendiente |
| Phase 2 | 3 | Scientific validation (HOLDOUT, GO/NO-GO) | Pendiente |
| Phase 3 | 4 | Producción (staging → blue/green → 10→100%) | Pendiente |
| Phase 4 | Ongoing | Monitoreo y tuning | Pendiente |

**Metas Phase 2 (GO):** cobertura ≥ 33.3% (+15pp), precisión ≥ baseline, FP < 1%, sin
regresiones HIGH/CRITICAL.

### 7.3 ADRs

- **ADR-001:** motor semántico — Phase 1-2 ✅, Phase 3 🔄 in design, 4-5 pendientes.
- **ADR-002:** migración del Decision Engine — Phase 0 actual.

---

## 8. Deuda técnica (resumen)

- **33 ítems** en backlog de estabilización (6 P0, 11 P1, 11 P2, 5 P3).
- **Sin tests:** `app_validacion.py` (1.340 líneas) y `parser_universal.py` (831 líneas).
- **Duplicación de código:** 15-20% (auditoría RC1).
- **Doble pipeline, doble parser, 4 motores de decisión, 2 backends** sin consolidar.

### Bugs críticos

| ID | Bug |
|---|---|
| C-1 | `app_validacion.py` sin tests, propagación automática sin verificación |
| C-2 | `parser_universal.py` sin tests |
| C-3 | Dos pipelines de clasificación sin tests de equivalencia |
| C-4 | 11 tests fallan en `test_split_ac01.py` |

### Deuda del conocimiento

- Catálogos polucionados (ej. "PROMESA OFICINA 22" → GASTOS con confianza alta).
- Gold standard auto-sembrado no confiable (exacto 38.4% en conflictos).
- Reglas R1/R4/R5 fuerzan `final_code` sin revisión.
- Bug TB-3 en `decision_v2/engine.py:496-528`.

---

## 9. Integridad / monitoreo

- **Runtime:** `gold_standard_runtime.db` (107 claves: 96 activas / 11 inactivas). Checksum del
  benchmark genera `0a60334706f9a8b9…`, verificable en P6.
- **Observabilidad P5.5:** uso del runtime, fallback al gold, uso efectivo del aprendizaje,
  impacto real de promociones.
- **Gates de release** definidos en `config/release.yml` (no leídos por código — ver A-4).

---

## 10. Siguientes pasos recomendados

1. Completar **diccionario** (RC05, 58.9% del unknown) y **catálogo CMCC** (RC06) → mayor salto
   de cobertura (→ ~91.8%).
2. Cerrar **Phase 1 del rollout CMCC** (shadow sobre todas las UNKNOWN).
3. Implementar **IDR (Sprint 22)** y **Confidence Engine (Sprint 23)** — críticos del roadmap.
4. Resolver **C-4 (split_ac01)** y añadir tests a `app_validacion.py` / `parser_universal.py`.
5. Ejecutar **Phase 2 scientific validation** (HOLDOUT, GO/NO-GO).