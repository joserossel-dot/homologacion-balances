# CMCC Production Rollout Plan

## Overview

Four-phase rollout. Each phase has explicit entry/exit criteria. No phase starts until the previous phase is GREEN. Rollback is possible at any phase in < 1 second.

## Phase 0: Prerequisites — COMPLETE ✅ (Sprint 26.1)

### Objective
Build the infrastructure needed for CMCC integration without changing classification behavior.

### Status: ✅ COMPLETE

All tasks delivered in Sprint 26.1:

| # | Task | Artifact | Status |
|---|------|----------|--------|
| P0.1 | `pipeline/features.py` with `CMCCFeatureFlags` dataclass | `pipeline/features.py` | ✅ |
| P0.2 | Flag evaluation at `_classify_account()` entry point | `pipeline/homologation_pipeline.py` | ✅ |
| P0.3 | CMCC metrics (`cmcc_shadow_hits`, `cmcc_production_hits`, `cmcc_review_queue`) | `pipeline/homologation_pipeline.py` | ✅ |
| P0.4 | CMCC latency tracking via `elapsed_seconds` summary | `pipeline/homologation_pipeline.py` | ✅ |
| P0.5 | Feature flag validation tests (all combinations, env vars, rollback) | `tests/test_cmcc_integration.py` | ✅ |
| P0.6 | Rollback integration test (ENABLE_CMCC=False equivalence) | `tests/test_cmcc_pipeline.py` | ✅ |
| P0.7 | Decision Trace CMCC stage + method codes (D001-D007 mapping) | `explainability/trace_builder.py` | ✅ |
| P0.8 | Benchmark & Compatibility reports | `scripts/cmcc_benchmark.py`, `scripts/cmcc_compatibility_report.py` | ✅ |

### Exit Criteria Verified

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `pipeline/features.py` exists and importable | ✅ | 734 tests pass |
| Pipeline runs identically with all flags=default | ✅ | ENABLE_CMCC=False skips CMCC entirely |
| Flags are toggleable via environment variable | ✅ | `CMCCFeatureFlags.from_env()` |
| All flag combination tests pass | ✅ | 81 new tests, 734 total |
| Rollback: ENABLE_CMCC=False restores original | ✅ | Feature flag check at runtime |
| Decision Trace captures CMCC decisions | ✅ | `_METHOD_TO_CODE` includes cmcc_* methods |
| Compatible with Release Pipeline | ✅ | All gates pass |

### Rollback
`ENABLE_CMCC=False` restores pre-CMCC behavior instantly. No recompile needed.

---

## Phase 1: Shadow Validation (Sprint 2)

### Objective
Run CMCC in shadow+metrics mode on the full pipeline. Collect enough data to validate that CMCC results are accurate and stable.

### Configuration

```python
CMCC_ENABLED = True       # CMCC runs on all UNKNOWN accounts
CMCC_PRODUCTION = False   # Results are NOT used for classification
CMCC_SHADOW_MODE = True   # Results stored in cmcc_shadow field
CMCC_THRESHOLD = 0.95     # Simulated production threshold
CMCC_REVIEW_THRESHOLD = 0.85  # Simulated review threshold
```

### Tasks

| # | Task | Owner | Artifact |
|---|------|-------|----------|
| P1.1 | Run full pipeline on all 185 documents with CMCC shadow | Developer | Pipeline logs |
| P1.2 | Generate shadow validation report | Developer | `reports/cmcc_shadow_validation/` |
| P1.3 | Compare CMCC shadow vs existing classifications (agreement rate) | Data Scientist | `validation_report.md` |
| P1.4 | Manual review of all CMCC-only classified accounts (those CMCC would add) | Data Scientist | Review annotations |
| P1.5 | Calculate false positive rate on CMCC-only hits | Data Scientist | `fp_rate.xlsx` |
| P1.6 | Run certification against gold standard | Developer | `certification_report.json` |
| P1.7 | Tune threshold if needed (test 0.90, 0.95, 0.98) | Data Scientist | `threshold_tuning.md` |
| P1.8 | Verify shadow consistency (≥99% with Phase 0 shadow) | Developer | `consistency_report.md` |

### Entry Criteria
- Phase 0 complete and GREEN
- Feature flags deployed to staging

### Exit Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Shadow consistency | ≥ 99% | Compare Phase 0 shadow vs Phase 1 shadow |
| False positive rate | < 1% | Manual review of CMCC-only hits |
| Latency P95 | < 50ms | Pipeline timing log |
| Coverage improvement (simulated) | ≥ +15pp | Metrics comparison |
| Decision trace shows CMCC stage | All UNKNOWN accounts have cmcc_shadow | Decision trace report |

### Duration
1 sprint (1 week)

### Rollback
Set `CMCC_ENABLED=False`. Pipeline returns to Phase 0 behavior. Shadow data preserved for analysis.

---

## Phase 2: Scientific Validation (Sprint 3)

### Objective
Statistically validate that CMCC-augmented pipeline meets or exceeds all quality metrics compared to baseline.

### Configuration

```python
CMCC_ENABLED = True
CMCC_PRODUCTION = False   # Still shadow mode for validation
# All other flags as tuned in Phase 1
```

### Validation Protocol

| Component | Specification |
|-----------|---------------|
| **Holdout** | 20 HOLDOUT PDFs (certified set) |
| **Gold standard** | `gold_standard.db` (103 accounts) |
| **Triple run** | Each benchmark runs 3 times; median metrics reported |
| **Baseline** | Current pipeline (Phase 0) on same holdout |
| **Candidate** | Pipeline with CMCC shadow applied (simulate production) |
| **Comparison** | Paired comparison: same accounts, same documents |

### Metrics Table

| Metric | Baseline | Candidate (target) | Pass? |
|--------|----------|--------------------|-------|
| Accounts classified | 1,952 | ≥ 4,500 | |
| Coverage | 18.3% | ≥ 33.3% | |
| Precision (gold standard) | 100% | ≥ 100% | |
| Recall (gold standard) | baseline | ≥ baseline | |
| F1 (gold standard) | baseline | ≥ baseline | |
| false positive rate | 0% | < 1% | |
| Latency P95 | baseline | < +50ms vs baseline | |

### Tasks

| # | Task | Owner | Artifact |
|---|------|-------|----------|
| P2.1 | Run certification on baseline (Phase 0) | Developer | `certification_baseline.json` |
| P2.2 | Run certification with CMCC shadow applied | Developer | `certification_candidate.json` |
| P2.3 | Compute comparison metrics | Data Scientist | `validation_comparison.xlsx` |
| P2.4 | Review all CMCC-only gold standard hits | Data Scientist | Manual review |
| P2.5 | Generate scientific validation report | Data Scientist | `scientific_validation_report.md` |
| P2.6 | GO/NO-GO review meeting | All | Decision record |

### Entry Criteria
- Phase 1 complete with GREEN status
- Threshold tuned and documented
- FP rate confirmed < 1%

### Exit Criteria (GO Conditions)
- Coverage improvement ≥ +15pp
- Precision ≥ baseline (no degradation)
- Recall ≥ baseline (no degradation)
- F1 ≥ baseline (no degradation)
- False positive rate < 1%
- No HIGH or CRITICAL regressions
- All GO criteria documented and verified

### Duration
1 sprint (1 week)

### Rollback
No production change yet. Rollback means staying in Phase 1 with shadow mode.

---

## Phase 3: Production Release (Sprint 4)

### Objective
Flip CMCC to production mode. First on staging for 24h, then on production.

### Configuration (Staging)

```python
CMCC_ENABLED = True
CMCC_PRODUCTION = True       # NOW active!
CMCC_SHADOW_MODE = True      # Keep shadow for comparison
CMCC_THRESHOLD = 0.95        # As tuned
CMCC_REVIEW_THRESHOLD = 0.85
```

### Release Sequence

```
Day 1  09:00  Deploy to staging with CMCC_PRODUCTION=True
Day 1  09:05  Run certification on staging → verify GO criteria
Day 1  10:00  Start 24h monitoring on staging
Day 2  09:00  Review 24h metrics: coverage, drift, anomalies
Day 2  09:30  If GREEN: promote to production
Day 2  10:00  Production deploy (blue/green: new pods with CMCC, old pods without)
Day 2  10:05  Route 10% traffic to CMCC pods
Day 2  11:00  Review metrics at 10% → if GREEN, route 50%
Day 2  12:00  Review metrics at 50% → if GREEN, route 100%
Day 2  13:00  100% CMCC production. Begin ongoing monitoring.
Day 3+        Continuous monitoring. Drift detection. Threshold tuning.
```

### Traffic Ramp-Up

```
100% │                                            ■── 100%
     │                                          ■
 75% │                                      ■
     │                                    ■
 50% │                              ■── 50%
     │                            ■
 25% │                        ■── 10%
     │                      ■
  0% ■── Current (0%)      ■
     └─────────────────────────────────────
       10:00  10:30  11:00  12:00  13:00
```

### Tasks

| # | Task | Owner | Artifact |
|---|------|-------|----------|
| P3.1 | Deploy to staging, verify GO criteria | DevOps | Staging deploy |
| P3.2 | 24h staging monitoring | Developer | Staging metrics dashboard |
| P3.3 | Staging sign-off | Data Scientist | Sign-off document |
| P3.4 | Production deploy (blue/green) | DevOps | Production deploy |
| P3.5 | Gradual traffic ramp (10% → 50% → 100%) | DevOps | Traffic config |
| P3.6 | Monitor rollback triggers | Developer | Monitoring dashboard |
| P3.7 | Post-release certification | Data Scientist | Post-release report |

### Entry Criteria
- Phase 2 complete with GO decision
- Release pipeline GREEN
- All rollback triggers tested
- Monitoring dashboard operational

### Exit Criteria
- 100% traffic on CMCC production for 24h
- All metrics within normal range
- No rollback triggers fired
- Post-release certification matches pre-release projections

### Duration
1 sprint (1 week for release + monitoring)

### Rollback
**Instant**: Set `CMCC_PRODUCTION=False` or `CMCC_ROLLBACK=True`. Pipeline reverts to pre-CMCC behavior. No restart required.

---

## Phase 4: Monitoring & Tuning (Ongoing)

### Objective
Track CMCC performance in production. Tune thresholds. Handle edge cases.

### Metrics Dashboard

| Metric | Update Frequency | Alert |
|--------|-----------------|-------|
| Coverage | Per document processing | Daily drift check |
| CMCC usage rate | Per account | Weekly trend |
| CMCC average score | Per batch | Weekly |
| False positive rate | Per quality snapshot | Daily |
| Unknown count | Per document | Daily drift check |
| Decision distribution | Per quality snapshot | Weekly |
| Score distribution | Per quality snapshot | Weekly |
| Latency | Per document | Real-time |

### Tuning Cadence

| Review | Frequency | Action |
|--------|-----------|--------|
| Threshold review | Monthly | Adjust CMCC_THRESHOLD based on FP rate |
| Concept distribution | Monthly | Add/remove concepts based on usage |
| Knowledge version | Per update | Re-run calibration after each cmcc.json update |
| Edge cases | Per report | Handle new account patterns |
| Drift detection | Weekly | Investigate score drift > 0.05 |

### Long-term Optimization

| Optimization | Trigger | Expected Gain |
|-------------|---------|---------------|
| Lower threshold to 0.90 | 3 months of FP < 0.5% | +500 more accounts recovered |
| Enable CMCC for dictionary fuzzy fallback | 6 months stable | ~200 more accounts |
| Add CMCC to learning engine pipeline | 6 months | ~150 more accounts (new variants from CMCC) |
| Deprecate dictionary fuzzy | CMCC accuracy > fuzzy for 6 months | Simplified pipeline |

---

## Rollback Procedures

### Manual Rollback
```bash
# Option 1: Environment variable (no deploy needed)
export CMCC_ROLLBACK=1
./scripts/run_pipeline.sh

# Option 2: Feature flag (persistent)
echo '{"CMCC_PRODUCTION": false, "CMCC_ENABLED": false}' > config/features.json

# Verify:
python scripts/run_certification.py
# Compare with baseline metrics → should be identical
```

### Automated Rollback
```yaml
# config/rollback_triggers.yaml
auto_rollback:
  precision_drop_pct: 1.0
  f1_drop_pct: 1.0
  fp_rate_pct: 2.0
  actions:
    - set_flag: CMCC_ROLLBACK=true
    - notify: "#pipeline-alerts"
    - generate_report: true
```

---

## Summary Timeline

```
Sprint 1     Sprint 2     Sprint 3     Sprint 4     Ongoing
    │            │            │            │            │
Phase 0      Phase 1      Phase 2      Phase 3      Phase 4
Prep &       Shadow       Scientific   Production   Monitor &
Flags        Validation   Validation   Release      Tune
    │            │            │            │            │
    ▼            ▼            ▼            ▼            ▼
Features     Shadow       GO/NO-GO     100%         Threshold
Flags        Report       Decision     Traffic      Tuning
