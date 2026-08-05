# Inventario de Normalizadores — Estado post-M2

Documento de FASE 1 del M3 (refactor arquitectónico del normalizador, sin cambio de comportamiento).
Fecha: 2026-08-03. Base: benchmark M2 = 2660/2662 (99.92%), 2 mismatches, 0 regresiones.

## Matriz de comportamiento (verificada con sonda real, 2026-08-03)

Sonda ejecutada sobre todos los normalizadores objetivo. Diferencias clave resaltadas.

| Input | N1 `exact_match` | N7 `unclassified_analyzer` | N10/N11 `reports` | N8 `unknown_cluster` | N13 `run_layout_validation` |
|---|---|---|---|---|---|
| `Vehículos` | `vehiculos` | `vehiculos` | `vehiculos` | `vehiculos` | `vehiculos` |
| `Muebles y Útiles` | `muebles y utiles` | `muebles y utiles` | `muebles y utiles` | `muebles y utiles` | `muebles y utiles` |
| `CAÑA` | `cana` | `cana` | `cana` | **`ca a`** | `cana` |
| `Señor` | `senor` | `senor` | `senor` | **`se or`** | `señor` |
| `ñandú` | `nandu` | `nandu` | `nandu` | **`andu`** | `ñandú` |
| `Übung` | `ubung` | `ubung` | `ubung` | **`bung`** | `Übung` |
| `Cta.Cte. Socios` | `cta cte socios` | `cta cte socios` | `cta cte socios` | `cta cte socios` | `cta.cte. socios` |
| `100%` | `100` | `100` | `100` | `100` | `100%` |
| `R.P.P. y H.` | `r p p y h` | `r p p y h` | `r p p y h` | `r p p y h` | `r.p.p. y h.` |

## Catálogo completo de normalizadores

### N1 — `learning/exact_match.py:7` (`normalize_name`, expuesta como `gs_normalize`)
- NFKD + eliminar combining marks + `lower().strip()` + `[^a-z0-9áéíóúñü ]+`→espacio + colapso espacios.
- Conserva á é í ó ú ñ ü (ya normalizados a forma NFC tras quitar diacríticos no-combinantes: los acentos se resuelven por NFKD+combining, el regex permite residuo).
- Resultado real: quita acentos, ñ→n, ü→u (vía NFKD/combining, sin `ascii`).
- **Usado por**: Learning Engine exact match (M2), `scripts/cmcc_official_benchmark.py`, `scripts/cmcc_scientific_validation.py`, `scripts/run_certification.py`, tests. **NO TOCAR en M3.**

### N2 — `pipeline/homologation_pipeline.py:76`
- `lower().strip()` + `[^a-z0-9áéíóúñü ]+`→espacio + colapso. **SIN NFKD**: conserva acentos y ñ/ü intactos.
- **NO TOCAR en M3** (Pipeline, fase futura).

### N3 — `decision_v2/engine.py:584`
- **SIN NFKD**. Regex `[^a-z0-9áéíóúñü\s]`→espacio (nótese `\s` vs `" "` en N1/N2) + colapso.
- **NO TOCAR en M3** (matching de producción).

### N4 — `app_validacion.py:87`
- `lower()` + quita acentos + `[^\w\s]`→espacio + colapso.
- **NO TOCAR en M3** (app en vivo; duplicada en `tools/audit_regex_precision.py`, `tools/analyze_legacy_gap.py`).

### N5 — `account_name_normalizer.py:295` (`AccountNameNormalizer`)
- Configurable: `lowercase`, `remove_accents`, `remove_symbols`, `collapse_spaces`, más abreviaciones, plurales, stopwords, corrección OCR.
- **NO TOCAR en M3** (clasificador de producción: `classification_engine`, `reglas_especiales`).

### N6 — `knowledge/normalizer.py:96`
- NFKD + encode ascii + lower + `[^\w\s]`→espacio + colapso. Alimenta CMCC (knowledge base).
- **NO TOCAR en M3** (CMCC excluido).

### N7 — `analytics/unclassified_analyzer.py:29` (`_normalize_name`)
- NFKD + ascii + `lower().strip()` + `[^\w\s]`→espacio + colapso. **Idéntica en resultado a N10/N11.**
- **OBJETIVO FASE 3** (migrar a `core.normalizer`).

### N8 — `knowledge/unknown_cluster.py:23` (`normalize_name`)
- `lower()` + re.sub manual por vocal áéíóú→a e i o u + `[^a-z0-9\s]`→espacio + colapso.
- **ELIMINA ñ, ü y cualquier no-ASCII** (no los convierte). Diverge de la familia NFKD en los 415 nombres con ñ y 45 con ü del corpus.
- **OBJETIVO FASE 3 — CON DIFERENCIA FUNCIONAL DETECTADA** (ver §Diferencias).
- Importada por `knowledge/synonym_detector.py:49,135` y `tests/test_knowledge_discovery.py` (API pública debe preservarse).

### N10 — `reports/architecture_state/analyze_baseline.py:56` (`normalizar`)
- NFKD + ascii + `lower()` + `[^\w\s]`→espacio + colapso + strip (sin strip inicial).
- **OBJETIVO FASE 3.** Alimenta `baseline_analysis.json`.

### N11 — `reports/run_pipeline_benchmark.py:50`, `reports/run_regex_fallback_benchmark.py:49`, `reports/analyze_unknown_pareto.py:58` (`normalizar`)
- NFKD + ascii + `lower().strip()` + `[^\w\s]`→espacio + colapso. Idénticas entre sí.
- `reports/analyze_unknown_pareto.normalizar` es importada por `reports/analyze_semantic_clusters.py:19` (migración transitiva; preservar símbolo `normalizar`).
- **OBJETIVO FASE 3.**

### N13 — `reports/run_layout_validation.py:65` (`_normalize_name`)
- Solo `lower().strip()` + colapso de espacios. **NO quita acentos ni símbolos.**
- **OBJETIVO FASE 3** → requiere `core.normalize(remove_accents=False, remove_symbols=False)`.

### Fuera de alcance FASE 3 (documentado para fase futura)
- N8b `knowledge_base/cmcc_builder.py:37` (`_normalizar`): idéntica a N1 original. CMCC excluido.
- `scripts/classification_gap_analysis.py:101,108`, `scripts/recovery_pareto.py:54`, `scripts/run_root_cause_analysis.py:50`, `scripts/cmcc_concept_audit.py:91`: scripts de análisis, fuera del alcance de FASE 3.
- `tools/validate_dictionary_audit.py:27`, `tools/dictionary_audit.py:67`: NFKD+UPPERCASE (semántica distinta: no minúscula). `tools/layout_audit.py:77`.
- `src/db_repository.py:125`: solo `.strip()` (no es normalizador).

## API objetivo de `core/normalizer.py` (FASE 2)

```python
def normalize(
    text: str,
    remove_accents: bool = True,
    collapse_spaces: bool = True,
    lowercase: bool = True,
    remove_symbols: bool = True,
    preserve_enye: bool = False,
) -> str
```

- Semántica default = familia N7/N10/N11 (NFKD + ascii-ignore + `[^\w\s]` + colapso).
- `preserve_enye=True` = conservar ñ literal (no convertir a n); cubre el futuro N1-variante.
- `remove_accents=False, remove_symbols=False` = familia N13 (run_layout_validation).

## Diferencias funcionales detectadas (regla de detención)

1. **N8 vs core.normalize (default)**: N8 elimina ñ/ü (415+45 nombres en corpus) y no aplica NFKD (p. ej. `CAÑA`→`ca a`, `Señor`→`se or`). La familia objetivo produce `cana`, `senor`. **No es posible migrar N8 a `core.normalize` sin cambio de comportamiento.**
2. **N13 vs default**: requiere `remove_accents=False, remove_symbols=False` (conserva acentos y símbolos). Migrable con parámetros explícitos.

> Pendiente de decisión: ver `reports/architecture_state/M3_report.md` — N8 podría migrarse aceptando la corrección de ñ (cambio de comportamiento, requiere aprobación explícita) o mantenerse intacta. Per regla M3, ante cualquier diferencia funcional se detiene y se reporta; **la migración de N8 queda EN ESPERA de aprobación.**

## Backup y estado

- Baseline M2: `/tmp/baseline_results_PRE_M2.json`, `/tmp/baseline_analysis_PRE_M2.json`, `/tmp/baseline_checkpoint_PRE_M2.json`.
- DB gold estado M1: `/tmp/gold_standard_baseline.db` (348 gold_records).
- Corpus de comparación FASE 4: `/tmp/m3_corpus.json` (17,655 nombres únicos; 4,875 no-ASCII; 415 con ñ; 45 con ü).
