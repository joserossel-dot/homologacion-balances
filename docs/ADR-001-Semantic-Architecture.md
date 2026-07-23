# ADR-001: Semantic Architecture for the Homologation Engine

**Status:** Draft  
**Date:** 2026-07-22  
**Author:** Architecture Team  
**Deciders:** Architecture Team  

---

## 1. System Objective

The Homologation Engine solves the problem of mapping account names from heterogeneous Chilean tax balance PDFs to a standardized Chart of Common Accounts (CMCC).

**The problem:**

- 182+ distinct PDF formats from different companies and ERPs
- Each format uses its own naming conventions, layout, and column structure
- PDFs are scanned or digitally generated, with varying OCR quality
- Manual mapping of account names to CMCC codes is slow, error-prone, and does not scale
- The set of ERPs grows continuously as new clients are onboarded

**The goal:**

Given a Chilean tax balance PDF, produce a machine-readable mapping of each account to its corresponding CMCC code with high precision and measurable recall, reducing the UNKNOWN rate to below 5% and minimizing human review effort.

---

## 2. General Architecture

```
 PDF
  │
  ▼
┌────────────────┐
│   ParserPDF    │  Extract text, tables, metadata
└────────────────┘
  │
  ▼
┌──────────────────┐
│  LayoutDetector  │  Identify layout type, column structure
└──────────────────┘
  │
  ▼
┌─────────────────────┐
│ AccountTypeResolver │  Determine account type from column context
└─────────────────────┘
  │
  ▼
┌──────────────────┐
│ AccountTypeFilter │  Filter non-account rows (totals, headers, noise)
└──────────────────┘
  │
  ▼
┌────────────────────┐
│ SemanticNormalizer │  Clean, expand, correct OCR, tokenize
└────────────────────┘
  │
  ▼
┌────────────────────┐      ┌─────────────────┐
│   SemanticMatcher  │◄─────│ Concept Catalog  │
└────────────────────┘      └─────────────────┘
  │
  ▼
┌──────────────────┐
│ CMCCClassifier   │  Assign final CMCC code with confidence
└──────────────────┘
  │
  ▼
┌────────────────┐
│ RegexFallback  │  Legacy patterns for unmatched accounts
└────────────────┘
  │
  ▼
┌───────────────┐
│ Human Review  │  Manual resolution of UNKNOWN accounts
└───────────────┘
```

### Stage Responsibilities

| Stage | Phase | Role |
|-------|-------|------|
| ParserPDF | 1 | Extract raw text and structured data from PDF |
| LayoutDetector | 1 | Detect balance type, orientation, column positions |
| AccountTypeResolver | 1 | Assign account type (ACTIVO/PASIVO/PATRIMONIO/PERDIDA) |
| AccountTypeFilter | 1 | Remove noise: totals, dates, page numbers, headers |
| **SemanticNormalizer** | **3** | Clean and standardize account names for matching |
| **SemanticMatcher** | **3** | Match normalized names to concepts via RapidFuzz |
| CMCCClassifier | 3 | Resolve concept → CMCC code with confidence |
| RegexFallback | 2 | Catch remaining accounts with legacy patterns |
| Human Review | 4 | Manual quality gate for UNKNOWN accounts |

---

## 3. Component Responsibilities

### 3.1 ParserPDF

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Extract all text content from a PDF file, preserving spatial layout |
| **Input** | PDF file path |
| **Output** | Raw text segments with (x, y, page) coordinates |
| **What it must NOT do** | Classify, interpret, or filter any extracted text |

### 3.2 LayoutDetector

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Identify the balance type and column layout from the extracted text |
| **Input** | Raw text segments from ParserPDF |
| **Output** | Layout type (CCA, CEA, EERR, etc.), column regions, row boundaries |
| **What it must NOT do** | Modify extracted text or interpret account names |

### 3.3 AccountTypeResolver

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Determine the account type (ACTIVO, PASIVO, PATRIMONIO, PERDIDA, GANANCIA) for each row based on its position within the layout |
| **Input** | Layout type + row boundaries from LayoutDetector |
| **Output** | Account type per row |
| **What it must NOT do** | Classify the account name or assign CMCC codes |

### 3.4 AccountTypeFilter

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Remove non-account rows: totals, subtotals, date headers, page numbers, empty rows |
| **Input** | Rows with account type from AccountTypeResolver |
| **Output** | Filtered list of likely-account rows |
| **What it must NOT do** | Modify account names or apply semantic classification |

### 3.5 SemanticNormalizer

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Normalize, clean, and standardize account names for semantic matching |
| **Input** | Raw account name string + account type |
| **Output** | Normalized token sequence |
| **What it must NOT do** | Classify or match against any catalog |

### 3.6 SemanticMatcher

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Match a normalized account name against the Concept Catalog to find the best-fitting concept |
| **Input** | Normalized account name + account type + Concept Catalog |
| **Output** | `ConceptMatch { concept_id, score, match_source, expected_cmcc, expected_account_type, confidence }` |
| **What it must NOT do** | Interpret numeric amounts, modify the Concept Catalog, or execute regex fallback |

### 3.7 CMCCClassifier

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Resolve a matched concept to a final CMCC code with confidence level |
| **Input** | ConceptMatch from SemanticMatcher |
| **Output** | CMCC code + confidence level + match detail |
| **What it must NOT do** | Re-match or overrule the SemanticMatcher's concept selection |

### 3.8 RegexFallback

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Catch accounts that the SemanticMatcher could not classify, using the legacy 7 regex rules (Phase 1) |
| **Input** | Account name (bypasses SemanticMatcher) |
| **Output** | CMCC code if a legacy pattern matches |
| **What it must NOT do** | Add new patterns or override SemanticMatcher results |

### 3.9 Human Review

| Aspect | Definition |
|--------|------------|
| **Responsibility** | Manual resolution of accounts that remain UNKNOWN after all automated stages |
| **Input** | UNKNOWN account list with suggested best_guess from SemanticMatcher |
| **Output** | Verified CMCC code assignment |
| **What it must NOT do** | Modify any automated component |

---

## 4. SemanticNormalizer

The SemanticNormalizer is the preprocessing stage that transforms a raw account name into a normalized, structured representation ready for semantic matching.

### 4.1 Normalization Pipeline

```
Raw account name
  │
  ▼
[1] Case folding:             "CAJA GENERAL" → "caja general"
  │
  ▼
[2] Unicode NFKD + ASCII fold: "remuneración" → "remuneracion"
  │
  ▼
[3] Punctuation removal:       "Cta. Cte." → "cta cte"
  │
  ▼
[4] Whitespace collapse:       "caja   general" → "caja general"
  │
  ▼
[5] Known abbreviation expand: "cxc" → "cuentas cobrar"
  │
  ▼
[6] Known OCR correction:      "banc0s" → "bancos"
  │
  ▼
[7] Stop-word removal:         "gastos de la administracion" → "gastos administracion"
  │
  ▼
[8] Tokenization:              → ["gastos", "administracion"]
  │
  ▼
Normalized token sequence
```

### 4.2 Abbreviation Expansion

Loaded from the Concept Catalog. Each concept defines its abbreviations. The normalizer maintains a global reverse map:

| Abbreviation | Expansion |
|-------------|-----------|
| cxc | cuentas cobrar |
| cxp | cuentas pagar |
| cta cte | cuenta corriente |
| ppe | propiedad planta equipo |
| ppm | pago provisional mensual |
| iva | impuesto valor agregado |
| ee.ff | estados financieros |
| ee.rr | estados resultados |

### 4.3 OCR Correction Rules

Static rule table for known OCR error patterns:

| Pattern | Correction |
|---------|-----------|
| `0` → `O` (in word context) | `banc0s` → `bancos` |
| `1` → `I` | `capìtal` → `capital` |
| `rn` → `m` | `rnuebles` → `muebles` |
| `vv` → `vv` | (already handled) → `w` |
| `5` → `S` | `5eguros` → `seguros` |
| `8` → `B` | `8ancos` → `bancos` |

### 4.4 Stop Words

The following words are removed during normalization as they carry no classificatory meaning:

```
de, la, el, del, los, las, un, una, y, e, o, a, por, al, con, en,
para, su, que, lo, no, se, entre, las, los, le, les, sus
```

### 4.5 Tokenization

The normalized string is split on whitespace. Each token must be ≥2 characters (single-character tokens are likely OCR artifacts). The resulting token sequence is the final output of the normalizer.

---

## 5. SemanticMatcher

The SemanticMatcher is the core classification engine. It compares a normalized account name against the Concept Catalog using RapidFuzz token_sort_ratio and selects the best-fitting concept.

### 5.1 API

```python
class SemanticMatcher:
    def __init__(self, catalog_path: str)
        """Load the Concept Catalog and build search indexes."""

    def match(
        self,
        account_name: str,
        account_type: Optional[str] = None,
    ) -> SemanticMatch:
        """Match a single account name to its best concept."""

    def match_batch(
        self,
        names: list[str],
        types: Optional[list[str]] = None,
    ) -> list[SemanticMatch]:
        """Batch match for performance (reuses preprocessed data)."""

    def get_concept(self, concept_id: str) -> ConceptInfo:
        """Retrieve a concept's full metadata from the catalog."""

    def explain(self, account_name: str) -> Explanation:
        """Return a human-readable explanation of the match decision."""
```

### 5.2 Input

| Field | Type | Description |
|-------|------|-------------|
| `account_name` | `str` | Normalized account name (output of SemanticNormalizer) |
| `account_type` | `Optional[str]` | Inferred account type (ACTIVO/PASIVO/PATRIMONIO/PERDIDA), used as type bonus |

### 5.3 Output

```python
@dataclass
class SemanticMatch:
    account_name: str          # Original input
    concept_id: str            # "CONCEPT_003" or None
    concept_name: str          # "BANCOS" or None
    score: float               # 0.0 – 1.0
    match_source: str          # "exact_keyword" | "synonym" | "abbreviation"
                               # | "fuzzy_keyword" | "fuzzy_synonym" | "root_word"
                               # | "none"
    expected_cmcc: str         # "AC.01" or "UNKNOWN"
    expected_account_type: str # "ACTIVO" or "UNKNOWN"
    confidence: str            # "ALTA" | "MEDIA" | "BAJA" | "NONE"
    details: str               # Human-readable explanation
```

### 5.4 Matching Algorithm

For each concept in the catalog:

1. **Tier 1 — Exact keyword match**: If `account_name` matches any keyword exactly → score = 1.0
2. **Tier 2 — Exact synonym match**: If `account_name` matches any synonym exactly → score = 0.95
3. **Tier 3 — Abbreviation match**: If `account_name` matches any abbreviation → score = 0.90
4. **Tier 4 — Fuzzy keyword match**: `rapidfuzz.fuzz.token_sort_ratio(account_name, keyword)` for each keyword → score = `ratio/100 × 0.85`
5. **Tier 5 — Fuzzy synonym match**: Same as Tier 4 but on synonyms → score = `ratio/100 × 0.75`
6. **Tier 6 — Root-word match**: If the first significant word of `account_name` matches the root word of the concept → score = 0.60
7. **Type bonus**: If `account_type` matches the concept's expected type → score `× 1.10`

The concept with the highest score is selected. If no concept scores ≥ 0.50, the account is returned as UNKNOWN with the best guess attached.

### 5.5 Confidence Levels

| Score Range | Confidence | Action |
|------------|-----------|--------|
| ≥ 0.90 | ALTA | Accept immediately |
| 0.70 – 0.89 | MEDIA | Accept, log for review sampling |
| 0.50 – 0.69 | BAJA | Accept only if Human Review is unavailable |
| < 0.50 | NONE | UNKNOWN — route to Human Review |

---

## 6. Concept Catalog

The Concept Catalog is the single source of truth for all accounting concepts. It is a versioned JSON file that decouples domain knowledge from code.

### 6.1 Format

```json
{
  "catalog": {
    "version": "1.0",
    "generated_date": "2026-07-22",
    "total_concepts": 78
  },
  "concepts": [
    {
      "id": "CONCEPT_001",
      "name": "BANCOS",
      "canonical_name": "Cuentas corrientes bancarias y disponible",
      "type": "ACTIVO",
      "expected_cmcc_code": "AC.01",
      "confidence": "ALTA",
      "keywords": ["banco", "bancos", "cuenta corriente", "cta cte"],
      "synonyms": ["disponible bancario", "efectivo en banco"],
      "abbreviations": ["c/c", "cc", "ctacte", "bco", "bcos"],
      "ocr_variants": ["banc0s", "bancos"],
      "common_errors": ["bancos"],
      "frequency": 320,
      "family_count": 125,
      "pct_of_gap": 3.2,
      "notes": ""
    }
  ]
}
```

### 6.2 Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier: `CONCEPT_NNN` |
| `name` | `str` | Yes | Short canonical name (e.g., "BANCOS") |
| `type` | `str` | Yes | Account type: ACTIVO/PASIVO/PATRIMONIO/PERDIDA |
| `expected_cmcc_code` | `str` | Yes | Primary CMCC code |
| `keywords` | `list[str]` | Yes | ≥1 root words for matching |
| `confidence` | `str` | Yes | ALTA/MEDIA/BAJA |

### 6.3 Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `canonical_name` | `str` | Full accounting definition |
| `synonyms` | `list[str]` | Alternative names for fuzzy matching |
| `abbreviations` | `list[str]` | Short forms (CxC, Cta Cte, ...) |
| `ocr_variants` | `list[str]` | Known OCR error forms |
| `common_errors` | `list[str]` | Common spelling mistakes |
| `frequency` | `int` | Total accounts in this concept |
| `family_count` | `int` | Number of distinct families |
| `pct_of_gap` | `float` | Percentage of UNKNOWN gap explained |
| `notes` | `str` | Free-text notes |

### 6.4 Versioning

The Concept Catalog follows semver: `MAJOR.MINOR`.

- **MAJOR**: Breaking changes (concept removal, field schema change)
- **MINOR**: Non-breaking additions (new concept, new keyword, new synonym)

Each catalog file includes a `version` field in its metadata. The version must be bumped on every change. The catalog URI is `knowledge/concept_catalog.v{major}.{minor}.json`; a symlink `knowledge/concept_catalog.json` always points to the current version.

### 6.5 Adding a New Concept

1. Create a new concept entry in the catalog JSON with all required fields
2. Populate keywords from the Pareto analysis of UNKNOWN accounts
3. Add any known synonyms, abbreviations, OCR variants, and errors
4. Bump MINOR version
5. Run the semantic matching benchmark to validate recall/precision
6. Commit and deploy

---

## 7. Classification Flow

The classification of an account proceeds through a strict decision hierarchy. Each stage has a higher recall but also a higher chance of false positives, so they are ordered from most precise (and fastest) to least precise (and slowest).

```
                    Account Name + Metadata
                             │
                             ▼
                    ┌─────────────────┐
                    │ 1. Code Match   │
                    │ (account_code  │
                    │  prefix → CMCC)│
                    └────────┬────────┘
                    YES↓     │NO
                 ┌────────┐  │
                 │ DONE   │  │
                 └────────┘  ▼
                    ┌──────────────────────┐
                    │ 2. Exact Dictionary  │
                    │ (known name → CMCC)  │
                    └──────────┬───────────┘
                    YES↓       │NO
                 ┌────────┐   │
                 │ DONE   │   │
                 └────────┘   ▼
                    ┌──────────────────────┐
                    │ 3. SemanticMatcher   │
                    │ (RapidFuzz + Catalog)│
                    └──────────┬───────────┘
                  score≥0.50↓  │score<0.50
                 ┌────────┐   │
                 │ DONE   │   ▼
                 └────────┘   ┌──────────────────────┐
                              │ 4. RegexFallback     │
                              │ (legacy patterns)    │
                              └──────────┬───────────┘
                              match↓     │no match
                             ┌────────┐  │
                             │ DONE   │  ▼
                             └────────┘  ┌──────────────────────┐
                                         │ 5. UNKNOWN          │
                                         │ → Human Review       │
                                         └──────────────────────┘
```

### Justification

| Order | Stage | Rationale |
|-------|-------|-----------|
| 1 | **Code Match** | Fastest (O(1) lookup), highest precision (100%), zero false positives. If the PDF includes account codes, use them. |
| 2 | **Exact Dictionary** | Second fastest (O(1) hash lookup), precision 100%. Covers previously seen accounts. |
| 3 | **SemanticMatcher** | Main classification engine. Handles unseen variants via fuzzy matching. Precision 88–95%, recall 75–88%. |
| 4 | **RegexFallback** | Safety net for accounts the semantic engine couldn't classify. The 7 legacy patterns have 100% precision but very low recall (2–3%). |
| 5 | **UNKNOWN** | Manual review for unresolved accounts. Fed back into the system as training data for continuous improvement. |

---

## 8. Metrics

### 8.1 Key Performance Indicators

| KPI | Definition | Target | Measurement |
|-----|-----------|--------|-------------|
| **Parser Accuracy** | % of correctly extracted account names vs. ground truth | ≥ 98% | Manual audit on 5% sample |
| **Semantic Recall** | % of UNKNOWN accounts that the SemanticMatcher correctly classifies | ≥ 80% | Automated benchmark against test set |
| **Semantic Precision** | % of SemanticMatcher classifications that are correct | ≥ 90% | Automated benchmark against test set |
| **Unknown Rate** | % of total accounts that remain UNKNOWN after all stages | < 5% | Pipeline log |
| **Review Rate** | % of accounts that require human review | < 3% | Pipeline log |
| **Average Confidence** | Mean confidence score of all classified accounts | ≥ 0.80 | Pipeline log |
| **Processing Time** | Total time to process one PDF | ≤ 30s | Benchmark |
| **Coverage** | % of 182 PDF formats that achieve ≥ 90% classification | 100% | Integration test |

### 8.2 Monitoring

All KPIs are computed per pipeline run and persisted to `reports/metrics_{timestamp}.json`. A dashboard (Streamlit) displays historical trends.

---

## 9. Feature Flags

All feature flags are defined in `CMCCFeatureFlags` and control the behavior of the pipeline at runtime.

### 9.1 Current Flags

| Flag | Default | Description |
|------|---------|-------------|
| `ENABLE_ACCOUNT_TYPE_FILTER` | `True` | Enable filtering of non-account rows |
| `ENABLE_REGEX_FALLBACK` | `True` | Enable legacy regex fallback |
| `ENABLE_PHASE2_CLASSIFIER` | `False` | Enable Phase 2 rapidfuzz classifier |
| `ENABLE_LAYOUT_DETECTOR` | `True` | Enable layout detection for column mapping |
| `DRY_RUN` | `False` | Generate report without modifying state |

### 9.2 Future Flags (Phase 3+)

| Flag | Default | Description |
|------|---------|-------------|
| `ENABLE_SEMANTIC_NORMALIZER` | `False` | Enable the SemanticNormalizer stage |
| `ENABLE_SEMANTIC_MATCHER` | `False` | Enable the SemanticMatcher stage |
| `ENABLE_CONCEPT_CATALOG` | `False` | Enable loading of the Concept Catalog |
| `MATCHER_ALTERNATIVE` | `"rapidfuzz"` | Selector: `"rapidfuzz"` or `"embeddings"` |
| `FUZZY_THRESHOLD` | `75` | Minimum RapidFuzz ratio for Tier 4/5 |
| `ENABLE_LEARNING` | `False` | Enable feedback loop from Human Review |
| `ENABLE_HUMAN_REVIEW_LOOP` | `False` | Enable active learning pipeline |

---

## 10. Architecture Principles

### 10.1 Component Isolation

1. **The Parser never classifies.** Extraction and interpretation are separate concerns.
2. **The SemanticMatcher never interprets amounts.** It operates only on account names.
3. **The RegexFallback is always the last automated resort.** Semantic matching must be attempted first.
4. **The Human Review never modifies automated code.** Feedback is captured as data, not patches.

### 10.2 Knowledge Decoupling

5. **Every concept belongs to the Concept Catalog.** No hard-coded concept knowledge in code.
6. **No rule may duplicate knowledge already in the catalog.** If a concept exists, the code may not hard-code it.
7. **The Catalog is versioned independently of code.** Concept updates do not require code deployment.

### 10.3 Matching Hierarchy

8. **Exact match always beats fuzzy match.** Precision is prioritized over recall at every tier.
9. **The SemanticMatcher always falls back gracefully.** UNKNOWN is a valid output, not an error.
10. **Confidence must accompany every classification.** Downstream consumers must be able to distinguish ALTA from BAJA.

### 10.4 Evolution

11. **New formats must not require code changes.** Adding support for a new PDF format must be achievable by updating the Concept Catalog only.
12. **Human Review output is training data.** Every manually resolved account is a candidate for catalog expansion.
13. **Metrics drive decisions.** No change is accepted without measured precision and recall impact.

---

## 11. Roadmap

### Phase 1: Parser Foundation (Complete)

```
[✓] ParserPDF: extract text from any PDF
[✓] LayoutDetector: detect CCA, CEA, EERR layouts
[✓] AccountTypeResolver: assign column-based account types
[✓] AccountTypeFilter: remove totals, headers, noise
[✓] 182 PDFs parsed and classified
```

### Phase 2: Pipeline Automation (Complete)

```
[✓] HomologationPipeline: end-to-end processing
[✓] CMCCFeatureFlags: runtime feature control
[✓] RegexFallback: 7 regex rules with 100% precision
[✓] UNKNOWN analysis: Pareto, semantic clusters
[✓] Concept Catalog: 78 concepts identified and documented
```

### Phase 3: Semantic Engine (Current — In Design)

```
[ ] SemanticNormalizer implementation
[ ] SemanticMatcher with RapidFuzz + Concept Catalog
[ ] CMCCClassifier integration
[ ] Benchmark against Phase 2 baseline
[ ] Production deployment alongside existing pipeline
```

### Phase 4: Learning System

```
[ ] Human Review feedback loop
[ ] Automatic catalog expansion from resolved UNKNOWN accounts
[ ] Threshold auto-tuning from historical matches
[ ] A/B testing framework for matching alternatives
[ ] Active learning: prioritize UNKNOWN accounts by impact
```

### Phase 5: Continuous Improvement

```
[ ] Performance monitoring dashboard
[ ] Automated retraining and catalog versioning
[ ] Drift detection: concept evolution over time
[ ] Multi-modal matching: code + name + amount correlation
[ ] Self-healing: automatic fallback to previous catalog version
```

---

## 12. Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| **OCR quality degradation** on new formats reduces match accuracy | High | Medium | SemanticNormalizer OCR correction layer + threshold tuning |
| **Concept ambiguity**: two distinct CMCC codes match the same keyword (e.g., "impuestos" → AC.07 or PC.05) | High | Medium | AccountType bonus + confidence scoring resolves ambiguity; ambiguous concepts logged for review |
| **Catalog drift**: concepts evolve as new formats are added, making existing keywords obsolete | Medium | Low | Semver versioning + regular catalog reviews every 100 new formats |
| **Performance degradation** as catalog grows beyond 78 concepts | Low | Low | Sub-linear index structure; 78 → 200 concepts is still < 10ms per account |
| **Team knowledge loss**: only one person understands the catalog semantics | Medium | Medium | Catalog is self-documenting JSON; every concept has notes and examples; ADR serves as onboarding doc |
| **False positives** from RapidFuzz on short account names (2–3 words) | Medium | Medium | Tier 1–3 (exact) prevent false positives; Tier 4–5 only active when score ≥ threshold |
| **Embedding lock-in**: if Phase 4 explores embeddings, migrating the catalog format may be costly | Low | Low | Catalog is format-agnostic (JSON); embeddings would add a vector index alongside, not replace |

---

## 13. Decisions

### 13.1 RapidFuzz + Concept Catalog over Embeddings

| Criterion | RapidFuzz + Catalog | Embeddings + Catalog |
|-----------|--------------------|----------------------|
| **Precision** | 88–95% | 85–92% |
| **Recall** | 75–88% | 80–90% |
| **Latency** | 2–5 ms/account | 50–200 ms/account |
| **Dependencies** | Already installed (rapidfuzz) | New: sentence-transformers, PyTorch |
| **Maintainability** | JSON-only updates | Retraining + model deployment |
| **Explainability** | Full: "score=0.85 con 'provedores' → 'proveedores'" | Black box |
| **Domain fit** | Excellent for 78 specific concepts | Overkill: embeddings can't distinguish GASTOS_ADMIN from GASTOS_VENTA |

**Decision rationale:**

- The domain has only 78 well-defined concepts. Embeddings excel at open-set problems (thousands of classes) but offer marginal recall gain over RapidFuzz for this small, specific set.
- OCR noise in the 182 PDFs is systematic (same substitutions across formats), so RapidFuzz with a few keyword variants captures most of it.
- Embeddings cannot distinguish between "Gastos de Administración" and "Gastos de Ventas" because they are semantically similar (both are expenses). RapidFuzz distinguishes them because the words "administración" and "ventas" are lexically different.
- RapidFuzz requires no GPU, no model download, and no specialized deployment infrastructure.
- The Concept Catalog approach allows a domain expert (accountant) to add concepts by editing JSON, not code or models.

**Decision:** RapidFuzz + Concept Catalog is the primary matching engine. Embeddings will be re-evaluated in Phase 4 if recall targets are not met.

### 13.2 Tiered Matching over Single-Pass

| Criterion | Tiered (6 tiers) | Single-pass (all fuzzy) |
|-----------|------------------|------------------------|
| **False positives** | Minimal (exact tiers act as gate) | Higher (fuzzy matches wrong concept) |
| **Performance** | Faster (early exit on exact match) | Slower (always fuzzy on all concepts) |
| **Explainability** | Clear match source per tier | Single opaque score |

**Decision:** 6-tier matching to maximize precision at every stage while maintaining high recall through progressive relaxation.

### 13.3 Concept Catalog over Hard-coded Rules

| Criterion | Concept Catalog | Hard-coded rules |
|-----------|----------------|------------------|
| **Update cost** | JSON edit (minutes) | Code change + deploy (hours) |
| **Accessibility** | Domain expert (accountant) | Developer only |
| **Versioning** | Native semver | Git-only (no catalog) |
| **Testing** | Single benchmark | Per-PR tests |

**Decision:** All domain knowledge lives in the Concept Catalog. The code is a generic matching engine with no accounting-specific logic.
