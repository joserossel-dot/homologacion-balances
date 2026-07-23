# ADR-002: Decision Engine v2 — Multi-Evidence Fusion

**Status:** Draft  
**Date:** 2026-07-22  
**Author:** Architecture Team  
**Deciders:** Architecture Team  

---

## 1. Context

The Homologation Pipeline currently has **7 independent classifiers**, each producing a candidate CMCC code with varying precision, recall, and confidence:

| # | Classifier | Abbreviation | Output |
|---|-----------|-------------|--------|
| 1 | Código Contable | `code` | CMCC code from account code prefix |
| 2 | Diccionario Exacto | `dict_exact` | CMCC code from exact dictionary match |
| 3 | Diccionario Fuzzy | `dict_fuzzy` | CMCC code from fuzzy dictionary match (≥90%) |
| 4 | SemanticMatcher (Tiers 1–6) | `semantic` | CMCC code + score + tier + concept |
| 5 | RegexFallback (7 audited rules) | `regex` | CMCC code from regex pattern match |
| 6 | AccountTypeResolver | `tipo` | Account type (ACTIVO/PASIVO/PATRIMONIO/...) |
| 7 | AccountTypeFilter | `filter` | Validate code prefix matches account type |

**Additional signals:**
- LearningEngine (Gold Standard SQLite — `learning_exact`, `learning_fuzzy`)
- CMCCClassifier (shadow mode — `cmcc`)

---

## 2. Classifier Performance Analysis

Based on the benchmark of **11,696 accounts** across 182 PDFs:

### 2.1 SemanticMatcher (n=4,130 classified, 35.3%)

| Tier | Accounts | Avg Score | Reliability | Rule |
|------|----------|-----------|-------------|------|
| 1 (Exact keyword) | 754 | 1.000 | **Gold** | Always wins |
| 2 (Exact synonym) | 268 | 0.950 | **Gold** | Always wins |
| 3 (Abbreviation) | 0 | — | (unused) | — |
| 4 (Fuzzy keyword) | 1,135 | 0.658 | Moderate | Wins with conditions |
| 5 (Fuzzy synonym) | 350 | 0.649 | Moderate | Wins with conditions |
| 6 (Root word) | 1,623 | 0.600 | Low | Loses to regex_exact |
| UNKNOWN | 7,566 | — | — | Defers to other classifiers |

**Key insight:** Tiers 1–2 are infallible (754 + 268 accounts). Tiers 4–6 have avg score < 0.70 and should be challenged by higher-precision classifiers.

### 2.2 Código Contable (n=127)

| Metric | Value |
|--------|-------|
| SM agreement (when both classify) | **0%** (0/20 conflicts) |
| SM-unknown cases captured | 107 (84.3%) |
| Avg SM score when in conflict | 0.658 (Tier 4.7) |
| Precision estimate | **Low** (0% vs SM, but SM is weak in conflicts) |

**Rule:** Wins only when account code maps unambiguously AND no higher-priority classifier has a strong match. Excellent as a fallback for SM-unknown cases.

### 2.3 Diccionario Exacto (n=152)

| Metric | Value |
|--------|-------|
| SM agreement (when both classify) | **21.7%** (33/152) |
| SM-unknown cases captured | 74 (48.7%) |
| SM conflicts lost | 45 (all vs SM, avg SM score 0.690) |
| Precision estimate | **High** (~95%) |

**Rule:** Wins over SM Tier 4–6, loses to SM Tier 1–2. Comparable to regex_exact in priority.

### 2.4 Diccionario Fuzzy (n=120)

| Metric | Value |
|--------|-------|
| SM agreement (when both classify) | **19.2%** |
| SM-unknown cases captured | 61 (50.8%) |
| SM conflicts lost | 36 (avg SM score 0.642) |
| Precision estimate | **Moderate** (~80%) |

**Rule:** Wins only when fuzzy score ≥95% AND SM tier ≥4. Loses to SM Tier 1–3 and regex_exact.

### 2.5 RegexFallback (n=202)

| Metric | Value |
|--------|-------|
| SM agreement (when both classify) | **8.9%** (18/202) |
| SM-unknown cases captured | **174 (86.1%)** |
| Precision guarantee | **100%** (audited rules) |

**Critical insight:** Regex has the lowest agreement with SM (8.9%) but captures the most SM-unknown cases (174). It is the best gap-filler. When regex and SM disagree, SM has avg score 0.648 (Tier 4.0), which is low.

**Rule:** Regex wins unconditionally when SM is unknown. When both classify, regex exact wins over SM Tier 4–6, loses to SM Tier 1–2.

### 2.6 LearningEngine — Gold Standard (n=554)

| Source | Accounts | SM agreement | SM-unknown captured |
|--------|----------|-------------|-------------------|
| learning_exact | 473 | 35.5% (168/473) | 127 (26.8%) |
| learning_fuzzy | 81 | 28.4% (23/81) | 28 (34.6%) |

**Rule:** Gold Standard exact wins over all classifiers except SM Tier 1–2. Gold Standard fuzzy comparable to dict_fuzzy.

### 2.7 AccountTypeFilter (n=variable per run)

| Action | Impact |
|--------|--------|
| Reject code-type mismatch | Prevents impossible codes (e.g., AC.01 for a PASIVO account) |
| Silent correction | Reduces false positives at near-zero cost |

**Rule:** Always applied as a post-classification guard. If ALL classifiers are rejected, mark as UNKNOWN.

---

## 3. Decision Engine v2 — Design

### 3.1 Architecture

```
 Account Name + Code + Type
         │
         ▼
 ┌──────────────────────────────────────┐
 │            EVIDENCE COLLECTOR         │
 │  Gathers all 7 classifier outputs     │
 │  into a unified evidence list         │
 └────────────┬─────────────────────────┘
              │
              ▼
 ┌──────────────────────────────────────┐
 │         ACCOUNT TYPE FILTER           │
 │  Removes codes incompatible with      │
 │  the account type                     │
 └────────────┬─────────────────────────┘
              │
              ▼
 ┌──────────────────────────────────────┐
 │         SCORING ENGINE                │
 │  Weighted fusion of evidence          │
 │  Computes: final_code, score,         │
 │  confidence, explanation              │
 └────────────┬─────────────────────────┘
              │
         ┌────┴────┐
         ▼         ▼
 ┌────────────┐ ┌────────────┐
 │ AUTO-DECIDE│ │ HUMAN      │
 │ (score ≥   │ │ REVIEW     │
 │ threshold) │ │ (score <   │
 └────────────┘ │ threshold) │
                └────────────┘
```

### 3.2 Evidence Collection

Each classifier produces:

```python
@dataclass
class Evidence:
    source: str          # Classifier ID
    proposed_code: str   # Proposed CMCC code (or None)
    score: float         # 0.0 – 1.0 confidence in this proposal
    tier: int            # If SemanticMatcher: 1–6; other methods: 0
    method: str          # Detailed method name
    explanation: str     # Human-readable explanation
    account_type: str    # Account type constraint
```

### 3.3 Priority Matrix

When multiple classifiers propose **different** codes, the following matrix resolves conflicts.

**Horizontal axis:** Classifier A (higher priority)  
**Vertical axis:** Classifier B (lower priority)  

| A \ B | Code | DictExact | DictFuzzy | SM T1 | SM T2 | SM T4 | SM T5 | SM T6 | Regex | GS Exact | GS Fuzzy |
|-------|------|-----------|-----------|-------|-------|-------|-------|-------|-------|----------|----------|
| **Code** | — | B | B | B | B | A | A | A | B | B | B |
| **DictExact** | A | — | A | B | B | A | A | A | Tie | Tie | A |
| **DictFuzzy** | A | B | — | B | B | Tie | A | A | B | B | Tie |
| **SM T1** | A | A | A | — | A | A | A | A | A | A | A |
| **SM T2** | A | A | A | B | — | A | A | A | A | A | A |
| **SM T4** | B | B | Tie | B | B | — | A | A | Tie | B | A |
| **SM T5** | B | B | B | B | B | B | — | A | B | B | B |
| **SM T6** | B | B | B | B | B | B | B | — | B | B | B |
| **Regex** | A | Tie | A | B | B | Tie | A | A | — | Tie | A |
| **GS Exact** | A | Tie | A | B | B | A | A | A | Tie | — | A |
| **GS Fuzzy** | A | B | Tie | B | B | B | A | A | B | B | — |

**A = Classifier A wins | B = Classifier B wins | Tie = Defer to tie-breaking rules**

**Priority tiers (1 = highest):**

| Tier | Classifiers | Condition |
|------|-------------|-----------|
| 1 | SM T1, SM T2 | Infallible. Always win. |
| 2 | Regex (exact match), GS Exact, DictExact | High precision (>95%). Win over lower tiers. |
| 3 | Code, DictFuzzy (≥95%), SM T4 | Moderate precision. Win only when score ≥ threshold. |
| 4 | GS Fuzzy, SM T5 | Lower precision. Win only with corroboration. |
| 5 | SM T6 | Weakest. Always loses except when alone. |

### 3.4 Tie-Breaking Rules

When two classifiers in the same priority tier propose different codes:

**Rule TB-1: Score comparison**
- If both classifiers have numerical scores, the higher score wins.
- If scores are within 0.05 of each other → TB-2.

**Rule TB-2: Precision tiebreaker**
- If one classifier has proven higher historical precision (from benchmark data), it wins.
- Historical precision: `regex_exact > dict_exact > gs_exact > code > dict_fuzzy > gs_fuzzy > sm_tier_4 > sm_tier_5 > sm_tier_6`

**Rule TB-3: Account type bonus**
- If one proposal's code matches the account type and the other does not, the type-matching code wins.

**Rule TB-4: Frequency bonus**
- If one proposal's code appears more frequently in the gold standard for similar account names, it wins.

**Rule TB-5: Human review escalation**
- If none of TB-1 through TB-4 produces a clear winner → **HUMAN_REVIEW**.

### 3.5 Final Score Calculation

The final score is computed as a **weighted ensemble** of all evidence:

```
final_score = Σ(w_i × score_i) / Σ(w_i)
```

Where:
- `w_i` = evidence weight based on method and conditions
- `score_i` = individual classifier's confidence score

**Evidence Weights:**

| Classifier | Base Weight | Modifiers |
|------------|-------------|-----------|
| SM Tier 1 | 1.00 | — |
| SM Tier 2 | 0.95 | — |
| SM Tier 4 | 0.60 | +0.10 if account_type matches |
| SM Tier 5 | 0.50 | +0.10 if account_type matches |
| SM Tier 6 | 0.40 | +0.05 if account_type matches |
| Regex exact | 0.85 | +0.10 if pattern is multi-word |
| Dict exact | 0.90 | — |
| Dict fuzzy | 0.60 | +0.05 per % above 90 |
| Code | 0.50 | +0.20 if 1-to-1 mapping |
| GS exact | 0.90 | — |
| GS fuzzy | 0.60 | — |

**Consensus bonus:**
- If ≥2 classifiers propose the same code: `final_score × 1.15` (capped at 1.0)
- If ≥3 classifiers propose the same code: `final_score × 1.25` (capped at 1.0)

**Conflict penalty:**
- If 2+ classifiers propose different codes and no consensus ≥2: `final_score × 0.80`

### 3.6 Confidence Labels

| Final Score | Label | Action |
|-------------|-------|--------|
| ≥ 0.95 | VERY_HIGH | Auto-accept. No review. |
| ≥ 0.85 | HIGH | Auto-accept. Log for sampling audit. |
| ≥ 0.70 | MEDIUM | Auto-accept. Log for regular audit. |
| ≥ 0.50 | LOW | Accept only in production. Flag for human review. |
| < 0.50 | UNKNOWN | Route to human review. |

### 3.7 Human Review Cases

Human review is required when:

**Case HR-1: Conflict unresolved**
- Two or more classifiers propose different codes AND tie-breaking fails.
- Criteria: TB-5 triggered.

**Case HR-2: All classifiers disagree**
- Every classifier proposes a different code (≥3 distinct proposals).
- Criteria: No consensus ≥2, all scores < 0.70.

**Case HR-3: Low confidence consensus**
- Two classifiers agree on a code but all scores < 0.70.
- Criteria: Consensus exists but weighted score < 0.50.

**Case HR-4: SM Tier 1–2 contradicts all others**
- Rare: SM T1/T2 conflicts with 3+ other classifiers (gold standard + regex + dict).
- Criteria: SM T1/T2 vs ≥3 other classifiers, all proposing a different common code.
- Resolution: Log incident, SM still wins but flag for audit.

**Case HR-5: Type filter rejects everything**
- All proposed codes are incompatible with account type.
- Criteria: After filtering, 0 classifiers remain.

### 3.8 Audit Metrics

Every decision is logged with:

```json
{
  "account_name": "Proveedores Varios",
  "account_code": "12345",
  "account_type": "PASIVO",
  "final_code": "PC.08",
  "final_score": 0.87,
  "confidence_label": "HIGH",
  "review_required": false,
  "decision_source": "consensus",
  "evidence": [
    {
      "source": "semantic",
      "proposed_code": "PC.08",
      "score": 0.85,
      "tier": 4,
      "method": "fuzzy_keyword",
      "explanation": "Coincidencia fuzzy con PROVEEDORES (score=0.85)"
    },
    {
      "source": "regex",
      "proposed_code": "PC.08",
      "score": 0.90,
      "tier": 0,
      "method": "pattern_19",
      "explanation": "Patrón auditado: acreedores varios"
    }
  ],
  "consensus_count": 2,
  "conflict_count": 1,
  "timestamp": "2026-07-22T14:00:00"
}
```

**Aggregate metrics per run:**

| Metric | Description | Target |
|--------|-------------|--------|
| **Auto-decision rate** | % of accounts resolved without human review | ≥ 95% |
| **Consensus rate** | % of decisions where ≥2 classifiers agree | ≥ 80% |
| **Conflict rate** | % of decisions where classifiers disagree | < 10% |
| **Human review rate** | % of accounts routed to human review | < 5% |
| **Avg confidence** | Mean final_score of all auto-decisions | ≥ 0.85 |
| **Precision@0.95** | Precision of decisions with score ≥ 0.95 | ≥ 99% |
| **Recall@0.70** | % of total accounts resolved at ≥ 0.70 confidence | ≥ 80% |
| **SM override rate** | % where SM is overridden by another classifier | < 5% |
| **Error cascade rate** | % where wrong auto-decision is corrected post-hoc | < 1% |

**Per-classifier tracking:**

| Metric | Description |
|--------|-------------|
| **Each classifier's contribution** | % of final decisions where it was the primary evidence |
| **Each classifier's override rate** | % of its proposals that were overridden |
| **Conflict pair frequency** | Most common classifier pairs that conflict |
| **False positive rate per method** | Measured from human review corrections |

---

## 4. Integration with ConfidenceEngine

The DecisionEngine v2 feeds its `final_score` and `confidence_label` into the ConfidenceEngine, which enriches the decision with:

- **Decomposition:** Score breakdown by evidence source
- **History:** Rolling precision tracking per classifier
- **Calibration:** Platt scaling adjustments based on historical correctness
- **Explanation:** Human-readable narrative of why a particular code was chosen

The ConfidenceEngine does **not** override the DecisionEngine's code selection. It only annotates and contextualizes.

---

## 5. Edge Cases

### 5.1 Solo Classifier

One classifier produces a code; all others are UNKNOWN.

```
→ Accept the proposal.
→ Confidence = classifier's score × 0.90 (solo penalty).
→ Exception: SM T6 solo → confidence capped at 0.50 (LOW).
```

### 5.2 All Unknown

All classifiers return UNKNOWN.

```
→ Output UNKNOWN.
→ route to Human Review.
→ Confidence = 0.0.
```

### 5.3 Type Filter Kills All Proposals

Every proposed code is incompatible with account type.

```
→ Output UNKNOWN.
→ route to Human Review with note: "Type filter rejected all proposals".
→ Confidence = 0.0.
```

### 5.4 SemanticMatcher Disabled

When `ENABLE_SEMANTIC_MATCHER=False`:
- Fall back to first-match-wins (original Phase 1 logic)
- DecisionEngine v2 still runs but with SM evidence absent

### 5.5 Complete Agreement (all ≥2)

All classifiers that have a proposal agree on the same code.

```
→ Accept immediately.
→ Score = weighted ensemble (consensus bonus ×1.25).
→ Confidence label from score.
→ No human review.
```

---

## 6. Rules Summary

| ID | Rule | Priority | Condition |
|----|------|----------|-----------|
| R1 | SM Tier 1–2 always wins | Absolute | SM tier 1 or 2 |
| R2 | Consensus ≥2 wins (no conflict) | 1 | ≥2 classifiers agree on same code |
| R3 | SM Tier 4 vs regex: regex wins | 2 | regex exact AND SM tier ≥4 |
| R4 | Dict exact vs SM T4–6: dict wins | 2 | dict exact AND SM tier ≥4 |
| R5 | GS exact vs SM T4–6: GS wins | 2 | GS exact AND SM tier ≥4 |
| R6 | Regex exact vs Dict fuzzy: regex wins | 3 | regex exact AND dict fuzzy |
| R7 | Code vs SM T4–6: code wins | 3 | code maps AND SM tier ≥4 |
| R8 | Dict fuzzy (≥95%) vs SM T4: wins | 3 | fuzzy score ≥95% AND SM tier 4 |
| R9 | Solo classifier | 4 | Only one classifier has a proposal |
| R10 | Conflict → TB-1 to TB-5 | Tiebreak | Classifiers disagree |
| R11 | All unknown → Human Review | Fallback | No classifier has a proposal |
| R12 | Type filter rejects all → Human Review | Fallback | All proposals type-incompatible |

**Evaluation order:** R1 → R2 → R3→R4→R5 → R6→R7→R8 → R9 → R10 → R11→R12

---

## 7. Migration Path

### Phase 0 (Current — DecisionEngine v1)
- Only SM vs Regex, 5 rules
- Code + Dict are first-match-wins before SM

### Phase 1 (DecisionEngine v2 — Parallel Run)
- All classifiers run in parallel
- DecisionEngine v2 produces a decision alongside existing v1
- Both outputs logged to `decision_engine_v2_comparison.json`
- No production impact

### Phase 2 (DecisionEngine v2 — Shadow Mode)
- DecisionEngine v2 runs as shadow, writing audit trail
- v1 still makes final decision
- Metrics compared between v1 and v2

### Phase 3 (DecisionEngine v2 — Production)
- v2 becomes the default
- v1 retained as emergency rollback
- Feature flag: `ENABLE_DECISION_ENGINE_V2=False` (default)

---

## 8. Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| **Consensus heuristic fails for ambiguous concepts** (e.g., "impuestos" could be AC.07 or PC.05) | High | Medium | Type filter resolves by account type; remaining ambiguous cases flagged for human review |
| **Over-confidence from consensus bonus** when 2 classifiers agree on wrong code | Medium | Low | Consensus bonus capped at 1.25×; human review threshold at 0.50 ensures minimum score |
| **SM Tier 1–2 regressions** (concept catalog bug causes wrong Tier 1 match) | High | Low | SM Tier 1–2 logged for audit; HR-4 flags unexpected contradictions |
| **Decision engine latency** from running all 7 classifiers | Low | Low | Evidence collection is parallelizable; total < 50ms per account |
| **Tie-breaking becomes too complex** to maintain | Medium | Medium | Rules are deterministic and documented; if rules need revision, update ADR and regenerate |
| **Gold Standard corruption** leads to wrong GS exact/fuzzy proposals | Medium | Low | GS is a SQLite DB with backups; GS is overridden by SM T1–2 and by regex exact |

---

## 9. Decisions

### 9.1 Weighted Ensemble over Hard Rules

| Criterion | Weighted Ensemble | Hard Rules | Machine Learning |
|-----------|------------------|------------|------------------|
| **Explainability** | Medium (weights are interpretable) | High (if-then is transparent) | Low (black box) |
| **Precision** | High (smooth handling of edge cases) | High (deterministic) | Variable (depends on training data) |
| **Maintenance** | Medium (weights need periodic calibration) | High (easy to add/remove rules) | Low (needs retraining) |
| **Cold start** | Immediate | Immediate | Requires labeled dataset |
| **Account conflicts** | Smooth (weights blend disagreement) | Binary (one rule wins) | Probabilistic |

**Decision:** Weighted ensemble with hard-rule overrides for SM T1–2. The hard rules handle the infallible cases (SM T1–2), while the weighted ensemble provides graceful degradation for ambiguous cases.

### 9.2 Parallel Collection over Sequential Pipeline

All 7 classifiers run in parallel on the same input. The Sequential pipeline (code → dict → SM → regex) is the fallback when `ENABLE_SEMANTIC_MATCHER=False`.

**Rationale:** Parallel collection captures the full evidence surface. The sequential pipeline artificially limits evidence (e.g., a regex match can only fire if SM fails, even though both might agree).

### 9.3 Consensus Bonus over Max Score

When 2+ classifiers agree on the same code, their collective vote is weighted more heavily than any single high-confidence classifier.

**Rationale:** Two moderate-confidence classifiers agreeing (e.g., dict fuzzy + regex, both at 0.85) is more reliable than one high-confidence classifier alone (SM T4 at 0.90). Historical data shows that cross-method agreement strongly correlates with correctness.

### 9.4 Solo Classifier Penalty over Blind Acceptance

A classifier running alone gets a 0.90 multiplier. SM T6 solo gets capped at 0.50.

**Rationale:** Prevents over-confidence when only one method has an opinion. The SM T6 solo cap reflects its low historical precision (0.600 fallback score).

### 9.5 Shadow Deployment over Immediate Cutover

DecisionEngine v2 runs in parallel with v1 for one full benchmark cycle before becoming the primary.

**Rationale:** The 319 discrepancies from Phase 1 demonstrate that classifier disagreements are complex. Shadow deployment allows empirical validation of the priority matrix before committing to production decisions.
