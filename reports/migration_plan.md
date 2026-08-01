# Migration Plan — V1 → RC1

## Strategy: Replace Seat-by-Seat (No Big Bang)

V1 and V2 coexist. Every change must keep V1 working.
We "flip" one adapter at a time. Until all are flipped, V1 runs.

---

## Phase 0: Fix V2 Circular Dependencies (Day 1)

**Problem:** `KBAdapter` instantiates `HomologationPipeline`. `ParserAdapter` imports `parsear_excel` from `app_validacion`.

**Fix:**
1. `KBAdapter` — inject pipeline as constructor parameter, never import it
2. `ParserAdapter` — extract `parsear_excel` to `parser_universal.py` or move the import into the method body
3. `app_validacion.py` — add `import time` (fix NameError)

**Risk:** None. These are mechanical changes. V1 continues unchanged.

---

## Phase 1: Create ExportAdapter (Day 2-3)

**What:** Extract Excel export logic from `app_validacion.py` to `adapters/ExportAdapter.py`
**Why:** Lowest risk, highest value — disentangles 150+ lines from the monolith
**Engine:** `export_engine.py` in `engines/` (grouping + formatting logic)
**Verify:** `python -c "from adapters.ExportAdapter import ExportAdapter; ExportAdapter().execute(ctx)"`

---

## Phase 2: Wire V2 to Streamlit (Day 4-5)

**What:** Create `app_v2/` — new Streamlit multi-page app
**Pages:**
- `Home.py` — upload, config, run pipeline
- `pages/1_Resumen.py` — KPIs, coverage
- `pages/2_Revision.py` — review queue
- `pages/3_Balance.py` — normalized balance + export
- `pages/4_Diccionario.py` — knowledge base browser
- `pages/5_Aprendizaje.py` — gold builder stats

**Services layer:**
- `services/pipeline_runner.py` — calls `HomologationPipelineV2.run()`
- `services/export_service.py` — calls ExportAdapter
- `services/review_service.py` — review queue operations

**No engines modified.** V2 adapters call existing engines.

**Verify:** `streamlit run app_v2/Home.py` — full flow works for PDF + Excel

---

## Phase 3: Flip ParserAdapter (Day 6-7)

**What:** Make V2 parser the default; V1 falls back to its own parser
**Why:** Parser is the highest-risk component (PDF/image/Excel)
**Strategy:**
1. Run V2 parser alongside V1 parser in "shadow mode"
2. Compare outputs — log mismatches to `reports/parser_diff_{timestamp}.json`
3. After validation, flip flag `USE_V2_PARSER = True`

**Verify:** Run 50+ test documents; compare parse results

---

## Phase 4: Flip KBAdapter + DecisionAdapter (Day 8-10)

**What:** Wire knowledge_base and gold_standard lookups into V2
**Strategy:**
1. KBAdapter reads gold_standard.db directly (no circular import)
2. DecisionAdapter calls `decision/engine.py` without going through `HomologationPipeline`
3. Shadow mode: compare V1 vs V2 classifications for every account

**Verify:** `python tests/test_decision_parity.py` — >99% match rate

---

## Phase 5: Flip Remaining Adapters (Day 11-14)

- CoverageAdapter
- SelfQAAdapter
- ReviewAdapter

Each flipped with shadow mode + diff logging.

---

## Phase 6: Deprecate V1 (Day 15)

1. `app_v2/` becomes default launcher
2. `app_validacion.py` moved to `deprecated/` with README
3. All `from app_validacion import` replaced with adapter calls
4. `pipeline/homologation_pipeline.py` archived

---

## Rollback Plan

Every `USE_V2_*` flag defaults to `False`.
To rollback: set flag to `False`, restart. Zero data loss.
