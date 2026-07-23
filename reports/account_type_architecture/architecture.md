# AccountTypeResolver: Architecture Design

## Problem

Currently `parsear_linea()` in `parser_universal.py:510-520` hardcodes `ULTIMAS_COLS = [ACTIVO, PASIVO, PERDIDA, GANANCIA]`, assuming every PDF has exactly 4 numeric columns in that order. This is wrong for:

- 2-column layouts (only Activo/Pasivo)
- 6-column layouts (Debe/Haber + Activo/Pasivo/Perdida/Ganancia)
- Consolidated reports with Patrimonio as a separate column
- Documents where column order differs

Worse: **no component in the pipeline validates that a classified code is consistent with the column it came from**. A `PC.01` (Proveedores) classified from the Activo column is silently accepted.

---

## Proposed Solution: AccountTypeResolver

A new pipeline component that sits between `LayoutDetector` and `Clasificador`, enforcing that **every code assignment is validated against the account type implied by the source column**.

### Position in the Pipeline

```
PDF Text
  │
  ▼
Parser (parsear_linea)
  │  ← produces CuentaRaw(origen_columna, codigo, nombre, monto)
  ▼
LayoutDetector (detecta columnas reales del documento)
  │  ← produces DetectedLayout(columns, confidence)
  ▼
AccountTypeResolver ← NEW
  │  ← valida/desambigua/corrige según tipo de cuenta
  ▼
HomologationPipeline._classify_account()
  │  ← clasificación final (código, regex, diccionario, etc.)
  ▼
Resultado
```

---

### Responsibilities

1. **Derive expected account type from `origen_columna`**

   | `origen_columna` | Cuenta_type_expected |
   |---|---|
   | `activo` | `ACTIVO` |
   | `pasivo` | `PASIVO` o `PATRIMONIO` |
   | `perdida` | `PERDIDA` (ER deudora) |
   | `ganancia` | `GANANCIA` (ER acreedora) |
   | `deudor` | `ACTIVO` o `PERDIDA` (ambiguous) |
   | `acreedor` | `PASIVO` o `GANANCIA` (ambiguous) |
   | `desconocido` | sin restricción |

2. **Validate code-candidate against expected type** — given a candidate code (from regex, dictionary, or catalog), confirm its prefix matches the expected type:

   | Code prefix | Account type |
   |---|---|
   | `AC`, `ANC` | ACTIVO |
   | `PC`, `PNC`, `PAT` | PASIVO/PATRIMONIO |
   | `ER` (naturaleza=deudora) | PERDIDA |
   | `ER` (naturaleza=acreedora) | GANANCIA |

3. **Resolve ambiguous code pairs by column** (already partially implemented in `Etapa 0.5` and `_corregir_por_columna`):

   | Ambiguous name | Codes | Resolved by column |
   |---|---|---|
   | Relacionadas CP | `AC.06` / `PC.07` | activo→AC.06, pasivo→PC.07 |
   | Relacionadas LP | `ANC.05` / `PNC.04` | activo→ANC.05, pasivo→PNC.04 |
   | Arriendos | `ER.01` / `ER.04` | ganancia→ER.01, perdida→ER.04 |
   | Intereses | `ER.12` / `ER.09` | ganancia→ER.12, perdida→ER.09 |
   | Honorarios | `ER.01` / `ER.04` | ganancia→ER.01, perdida→ER.04 |
   | Comisiones | `ER.01` / `ER.05` | ganancia→ER.01, perdida→ER.05 |
   | Servicios | `ER.01` / `ER.04` | ganancia→ER.01, perdida→ER.04 |

4. **Detect contradictions** — if the catalog says `AC.01` has `categoria=activo_corriente` but `origen_columna=pasivo`, flag it.

5. **Correct `origen_columna` when code is known** — if code is `AC.01` and `origen_columna=desconocido`, set it to `activo`. This unlocks column-based disambiguation for accounts that lost their column during parsing.

---

### Input / Output Contract

```python
@dataclass
class AccountTypeResult:
    cuenta: CuentaRaw
    account_type: Optional[str]        # ACTIVO | PASIVO | PATRIMONIO | PERDIDA | GANANCIA
    validation: AccountTypeValidation  # OK | CORRECTED | CONTRADICTION | UNKNOWN
    correction_note: Optional[str]     # human-readable explanation

class AccountTypeResolver:
    def resolve(self, cuenta: CuentaRaw, layout: DetectedLayout) -> AccountTypeResult
```

---

### Integration Points to Existing Code

#### 1. `parser_universal.py:parsear_linea()` (lines 500-542)

The current `ULTIMAS_COLS` heuristic would remain as **fallback only**. When `LayoutDetector` returns `confidence >= 0.5`, its column order replaces `ULTIMAS_COLS` for that document.

**Change needed**: lift `ULTIMAS_COLS` out of `parsear_linea()` and pass it as a parameter. The caller (`parsear_pdf`) already has access to `LayoutDetector`.

#### 2. `app_validacion.py:clasificar()` Etapa 0.5 (lines 204-227)

This is the **current partial implementation** of column-based disambiguation. It handles exactly 7 ambiguous names. The `AccountTypeResolver` would:

- Generalize this to ALL codes (not just NOMBRES_AMBIGUOS)
- Move the logic from `app_validacion.py` into the pipeline
- Retain the existing `MAPA_AMBIGUO` dict as the reference table

#### 3. `app_validacion.py:_corregir_por_columna()` (lines 309-348)

This method is called to **reclassify** an already-classified account. Its logic (keyword + column → definitive code) would become the `AccountTypeResolver`'s post-validation correction step.

The bank-overdraft rule (line 331-335: negative monto + activo + keyword banco → `PC.02`) is a **special case** that should remain in the resolver.

#### 4. `adapters/account_adapter.py` (lines 8-15)

`_COLUMN_MAP` maps `origen_columna` → `AccountAmounts` field. This mapping is correct but **overloaded**: it conflates "where the number appeared" with "account type". The `AccountTypeResolver` would make this relationship explicit:

```python
# New: type→field mapping in AccountTypeResolver
_TYPE_TO_AMOUNT_FIELD = {
    "ACTIVO": "assets",
    "PASIVO": "liabilities",
    "PERDIDA": "losses",
    "GANANCIA": "profits",
}
```

The adapter would then use the **validated** `account_type` (not raw `origen_columna`) to set the amount field.

---

### Regex Patterns Impact

The precision audit (`reports/regex_audit/regex_precision.md`) identified:

- **7 safe patterns** (100% precision) → migrate as-is
- **8 patterns needing adjustment** → add column validation guard
- **10 patterns to eliminate** → remove from REGLAS_REGEX, keep in HomologationPipeline as post-correction only

With `AccountTypeResolver` in place, all 37 patterns can run **after** column validation, and any pattern that returns a code contradicting the column is demoted or discarded.

Example: pattern `\bventa\b` → `ER.01` (GANANCIA). If `origen_columna=perdida`, the resolver would block it.

---

### Column Correction Cases from HOLDOUT Analysis

On the 19 HOLDOUT PDFs (1333 accounts):

| Correction type | Count | Description |
|---|---|---|
| Regex recovery | 206/229 | Patterns recover accounts MotorHibridoLocal misses |
| Column post-correction | 18/229 | `_corregir_por_columna` changes code after regex hit |
| Column pre-disambiguation | 3/229 | Etapa 0.5 resolves ambiguous name before regex |
| **Total recovered** | **227/229 (99.1%)** | Only 2 accounts remain unrecovered |

The 18 post-correction cases **all depend on validated `origen_columna`**. Without `AccountTypeResolver`, these corrections are applied on the raw column (which may be wrong). The resolver makes them trustworthy.

---

### Implementation Plan

```
Phase 1 — Scaffold (safe, zero behavioral change)
  1. Create src/resolvers/account_type_resolver.py
  2. Implement resolve() with current hardcoded logic
  3. Add unit tests that pass against HOLDOUT corpus
  4. Confirm existing pipeline produces identical results

Phase 2 — LayoutDetector Integration
  1. Pass DetectedLayout through to parsear_linea()
  2. Replace ULTIMAS_COLS when layout.confidence >= 0.5
  3. Test against 2-column and 6-column documents

Phase 3 — Column Validation Gates
  1. Before classification: validate code prefix vs origin
  2. Reject contradictory candidates (confianza → 0)
  3. Migrate top-7 regex patterns into validated flow

Phase 4 — Ambiguo Unification
  1. Move Etapa 0.5 into AccountTypeResolver
  2. Move _corregir_por_columna into AccountTypeResolver
  3. Remove duplicated AMBIGUOS table from app_validacion.py
  4. Single source of truth for all 10+ ambiguous patterns
```

---

### Key Design Decision: Pipe vs. Decorator

| Approach | Pros | Cons |
|---|---|---|
| **Pipe** (explicit call in pipeline) | Traceable, testable, visible in logs | Requires pipeline refactor |
| **Decorator** (wraps classify()) | Minimal code change | Hidden logic, harder to debug |

**Verdict: Pipe**. The AccountTypeResolver gets an explicit call in `homologation_pipeline.py`, right after parsing and before classification. This makes the data flow visible and each stage independently testable.

---

### Future Considerations

- **origen_columna=deudor/acreedor**: 6-column layouts report Debe/Haber instead of Activo/Pasivo. The resolver maps deudor→{ACTIVO, PERDIDA} and acreedor→{PASIVO, GANANCIA}, which is inherently ambiguous. Resolution requires looking at the code prefix: if codigo starts with AC/ANC → ACTIVO, if PC/PNC/PAT → PASIVO, etc.
- **Consolidated vs. individual**: Some PDFs have Patrimonio as a 5th column. LayoutDetector should detect this; AccountTypeResolver should accept it.
- **signo_normal cross-check**: A future enhancement could validate that the monto sign matches signo_normal for the given code. E.g., PC.01 (signo_normal=-1) should have a negative or zero monto in the pasivo column.
