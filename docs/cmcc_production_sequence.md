# CMCC Production Integration — Sequence & Flow

## 1. Current Pipeline (as-is)

```
PDF/Excel
    │
    ▼
ParserPDF.parsear()
    │
    ▼
AccountAdapter → BalanceInterpreter → AccountBalance[]
    │
    ▼
For each account:
    │
    ├── 1. LearningEngine.best_match()
    │       ├── exact_match()        ──→ method="learning_exact",    conf=0.98
    │       └── fuzzy_match(thr=92)  ──→ method="learning_fuzzy",    conf=0.80-0.97
    │
    ├── 2. ClasificadorCodigo.clasificar()
    │                               ──→ method="code",              conf=0.85-0.97
    │
    ├── 3. Dictionary exact match
    │                               ──→ method="dictionary_exact",  conf=0.98
    │
    ├── 4. Dictionary fuzzy (thr=90)
    │                               ──→ method="dictionary_fuzzy",  conf=0.80-0.97
    │
    ├── 5. UNCLASSIFIED
    │       standard_code=None, confidence=0.0, method="unclassified"
    │
    ▼
CMCC Shadow (score >= 0.90)
    → stored as cmcc_shadow
    → NEVER affects standard_code
    →
    ▼
Semantic Shadow
    → diagnostic only
    →
    ▼
Special Rules (R1-R5)
    → overrides final_code
    →
    ▼
Result: classification_result[]
```

---

## 2. Proposed Pipeline (CMCC Production)

```
PDF/Excel
    │
    ▼
ParserPDF.parsear()
    │
    ▼
AccountAdapter → BalanceInterpreter → AccountBalance[]
    │
    ▼
For each account:
    │
    ├── 1. LearningEngine.best_match()
    │       ├── exact_match()
    │       └── fuzzy_match(thr=92)
    │
    ├── 2. ClasificadorCodigo.clasificar()
    │
    ├── 3. Dictionary exact match
    │
    ├── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
    │                     [ NEW ]
    ├── 4. CMCC PRODUCTION (threshold >= 0.95)
    │       CMCCFeatures.CMCC_PRODUCTION=True
    │       CMCCFeatures.CMCC_THRESHOLD=0.95
    │       │
    │       ├── CMCCClassifier.classify(account_name)
    │       │       → code, score, concept, method, evidence
    │       │
    │       ├── IF score >= 0.95:
    │       │   → standard_code = code
    │       │   → final_code = code
    │       │   → confidence = score
    │       │   → method = f"cmcc_{method}"
    │       │   → RETURN classified
    │       │
    │       ├── IF score >= 0.85 AND score < 0.95:
    │       │   → store as cmcc_review_queue (human review)
    │       │   → CONTINUE to next stage
    │       │
    │       └── IF score < 0.85:
    │               → CONTINUE to next stage
    │
    ├── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
    │
    ├── 5. Dictionary fuzzy (thr=90)
    │
    ├── 6. UNCLASSIFIED
    │       standard_code=None, confidence=0.0, method="unclassified"
    │
    ▼
CMCC Shadow (always, for monitoring)
    → still stores cmcc_shadow even in production mode
    → used for drift detection and comparison
    →
    ▼
Semantic Shadow
    → diagnostic only
    →
    ▼
Special Rules (R1-R5)
    → overrides final_code
    → IF CMCC assigned code AND rule overrides: document conflict
    →
    ▼
Result: classification_result[]
```

---

## 3. CMCC Classify Call Sequence

```
AccountBalance (account_name="Caja")
    │
    ▼
CMCCClassifier.classify("Caja")
    │
    ├── normalize("Caja") → "caja"
    │
    ├── _build_index() already called at __init__
    │   → all_variants = [(normalized, original, code, type), ...]
    │
    ├── For each variant in all_variants:
    │       score = _score("caja", variant_normalized)
    │       → rapidfuzz weighted: exact*0.4 + token_sort*0.3
    │                           + token_set*0.2 + partial*0.1
    │
    ├── Best score = 1.0 (exact match: "caja" → AC.01 Caja y Bancos)
    │
    └── Return: {code: "AC.01", concept: "Caja y Bancos",
                 score: 1.0, method: "cmcc_variante",
                 matched_variant: "caja", evidence: [...]}
```

---

## 4. Feature Flag Evaluation Flow

```
HomologationPipeline.process()
    │
    ▼
    features = CMCCFeatureFlags.from_env()
    │
    ▼
    _classify_account():
        │
        ├── learning_exact/fuzzy
        │
        ├── code
        │
        ├── dictionary_exact
        │
        ├── IF features.CMCC_ENABLED AND NOT features.CMCC_ROLLBACK:
        │       cmcc_result = _cmcc_classifier.classify(account_name)
        │       │
        │       ├── IF features.CMCC_PRODUCTION:
        │       │       IF cmcc_result.score >= features.CMCC_THRESHOLD:
        │       │           → USE cmcc_result AS classification
        │       │           → RETURN
        │       │
        │       ├── ALWAYS:
        │       │       → store cmcc_shadow (for monitoring)
        │       │   IF cmcc_result.score >= features.CMCC_REVIEW_THRESHOLD:
        │       │       → add to review_queue (for human review)
        │       │
        │       └── (continue to dictionary_fuzzy)
        │
        ├── IF NOT features.CMCC_ENABLED OR features.CMCC_ROLLBACK:
        │       → skip CMCC entirely (original behavior)
        │
        ├── dictionary_fuzzy
        │
        └── UNKNOWN
```

---

## 5. Shadow Consistency Verification

```
During validation phase (CMCC_PRODUCTION=False):

For each account in UNKNOWN:
    existing_shadow = stored cmcc_shadow (from shadow mode)
    new_cmcc = CMCCClassifier.classify(account_name)

    IF new_cmcc.score >= 0.95:
        IF existing_shadow exists AND existing_shadow.code == new_cmcc.code:
            → CONSISTENT ✓
        ELSE:
            → INCONSISTENT ⚠️ — log for review
            (should not happen: both use same CMCCClassifier)

Consistency rate target: ≥ 99%
```

---

## 6. Data Flow After CMCC Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Classification Result                        │
├──────────────────────────────────────────────────────────────────────┤
│ account_name          "Caja"                                         │
│ standard_code         "AC.01"                                        │
│ final_code            "AC.01"                                        │
│ confidence            0.95                                            │
│ method                "cmcc_variante"                                 │
│ reason                "Clasificado por CMCC (score=0.95, variante)"   │
│ cmcc_shadow           {code: "AC.01", score: 1.0, method: "cmcc_..."}│
│ semantic_result       {type: "asset", ...}                            │
│ special_rule_applied  null                                            │
└──────────────────────────────────────────────────────────────────────┘

The cmcc_shadow field preserves the raw CMCC score (which may differ from
the final confidence if the threshold is > 0.95). This allows monitoring
of CMCC behavior independent of threshold configuration.
```

---

## 7. Rollback Sequence

```
Manual Rollback:
    1. Set CMCC_ROLLBACK=True  (or CMCC_PRODUCTION=False, CMCC_ENABLED=False)
    2. Next account classification skips CMCC entirely
    3. Pipeline reverts to original 5-stage cascade
    4. Verify: run certification → metrics match pre-CMCC baseline

Automated Rollback:
    1. Quality monitor detects precision drop > 1pp
    2. Alert triggers → set CMCC_ROLLBACK=True
    3. Notification sent to pipeline operator
    4. Detailed report generated (affected accounts, drift delta)
```

---

## 8. Decision Boundary Diagram

```
CMCC Score
    │
  1.0 ┌─────────────────────────────────────────┐
    │ │      PERFECT MATCH                      │
    │ │      3,041 accounts (34.6% of UNKNOWN)   │
    │ │      → Production threshold: USE         │
    │ │      → method: cmcc_variante             │
  0.95├─────────────────────────────────────────┤
    │ │      HIGH CONFIDENCE                    │
    │ │      → Production threshold: USE         │
    │ │      → method: cmcc_{type}               │
    │ │                                           │
  0.85├─────────────────────────────────────────┤
    │ │      REVIEW QUEUE                        │
    │ │      → Human validation required         │
    │ │      → Store for review                  │
    │ │      → Continue to fuzzy/UNKNOWN         │
    │ │                                           │
  0.50├─────────────────────────────────────────┤
    │ │      LOW CONFIDENCE                     │
    │ │      → Ignore for classification         │
    │ │      → Store for drift monitoring        │
    │ │                                           │
  0.0 └─────────────────────────────────────────┘
```

---

## 9. Timeline: From Design to Production

| Phase | Duration | Activities | Outcome |
|-------|----------|------------|---------|
| **0. Prerequisites** | 1 sprint | Add feature flags, refactor CMCC call site, add metrics counters | Feature flag infrastructure |
| **1. Shadow Validation** | 1 sprint | Run CMCC in shadow+metrics mode on full pipeline (185 docs) | Validation report, threshold tuning |
| **2. Scientific Validation** | 1 sprint | Run certification against gold standard, triple benchmark | GO/NO-GO decision |
| **3. Production Release** | 1 sprint | Flip CMCC_PRODUCTION=True on staging, monitor 24h, roll to production | CMCC live in pipeline |
| **4. Monitoring & Tuning** | Ongoing | Track metrics, tune threshold, handle edge cases | Continuous improvement |
