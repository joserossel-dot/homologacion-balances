# Sprint 28.3 — AccountTypeResolver Report

**Date:** 2026-07-20

---

## Overview

New component `AccountTypeResolver` that determines the allowed account type universe for each parsed account using `origen_columna`, detected layout, and existing accounting rules.

**NO classification. NO regex. NO fuzzy matching. NO CMCC.**

### Output types

| Type | Meaning |
|------|---------|
| `ACTIVO` | Assets |
| `PASIVO` | Liabilities |
| `PATRIMONIO` | Equity |
| `PERDIDA` | Losses (debit-nature income statement) |
| `GANANCIA` | Profits (credit-nature income statement) |
| `DESCONOCIDO` | Cannot be determined |

---

## Design

### Derivation table

| `origen_columna` | Allowed types | Resolution strategy |
|---|---|---|
| `ACTIVO` | ACTIVO | Direct (unambiguous) |
| `PASIVO` | PASIVO, PATRIMONIO | Layout + code prefix: if layout has "patrimonio" and code starts with `PAT` → PATRIMONIO; else PASIVO |
| `PERDIDA` | PERDIDA | Direct |
| `GANANCIA` | GANANCIA | Direct |
| `DEUDOR` | ACTIVO, PERDIDA | Code prefix: `AC`/`ANC` → ACTIVO; `ER` → PERDIDA; `PC`/`PNC` → PASIVO; else ACTIVO fallback |
| `ACREEDOR` | PASIVO, GANANCIA | Code prefix: `PC`/`PNC`/`PAT` → PASIVO/PATRIMONIO; `ER` → GANANCIA; else PASIVO fallback |
| `DESCONOCIDO` | All 5 | Code prefix if available; else DESCONOCIDO |

### Code prefix rules

| Prefix | Type |
|--------|------|
| `ANC` | ACTIVO |
| `AC` | ACTIVO |
| `PNC` | PASIVO |
| `PC` | PASIVO |
| `PAT` | PATRIMONIO |
| `ER` + deudor col | PERDIDA |
| `ER` + acreedor col | GANANCIA |

### Feature flag

`ENABLE_ACCOUNT_TYPE_RESOLVER = False` in `parser_universal.py:41`. When `True`, each `CuentaRaw` receives a `tipo_cuenta` field after parsing.

### Integration point

```
ParserPDF.parsear()
  ├─ ... (parsing unchanged)
  ├─ [NEW] if ENABLE_ACCOUNT_TYPE_RESOLVER:
  │     for each cuenta:
  │       AccountTypeResolver.resolve(origen_columna, codigo, layout_columns)
  │       → c.tipo_cuenta = result.account_type.value
  └─ return ResultadoParseo
```

---

## Files Changed

### Only `parser_universal.py` modified

| # | Line | Change |
|---|------|--------|
| 1 | 41 | `ENABLE_ACCOUNT_TYPE_RESOLVER = False` |
| 2 | 88 | `tipo_cuenta: Optional[str] = None` on `CuentaRaw` |
| 3 | 619 | `layout_columns: Optional[list[str]] = None` capture |
| 4 | 658-668 | Post-processing: `AccountTypeResolver.resolve()` for each account |

### New file: `parsers/account_type_resolver.py`

- `AccountType` enum (6 values)
- `AccountTypeResult` dataclass (type, allowed_types, confidence, method, note)
- `AccountTypeResolver` class with `resolve()` method
- 139 lines total

### New file: `tests/test_account_type_resolver.py`

- 8 test classes, 36 test methods
- Covers: direct mapping, PASIVO ambiguity, DEUDOR/ACREEDOR resolution, DESCONOCIDO, code prefix ordering, integration

---

## Test Results

### `pytest tests/` (all tests)

| Result | Count |
|--------|-------|
| Passed | 905 |
| Failed | 14 (pre-existing in `test_split_ac01.py`) |
| New | 0 |

### `pytest tests/test_account_type_resolver.py`

| Result | Count |
|--------|-------|
| Passed | 36 |
| Failed | 0 |

---

## Validation — 182 Documents

| Metric | Value |
|--------|-------|
| PDFs processed | 182/182 (100%) |
| Errors | 0 |
| Documents with account count change | **0** |
| Total accounts resolved | 30,829 |

### Distribution by tipo_cuenta

| Type | Count | % |
|------|-------|---|
| DESCONOCIDO | 17,249 | 56.0% |
| GANANCIA | 5,384 | 17.5% |
| ACTIVO | 3,203 | 10.4% |
| PASIVO | 2,499 | 8.1% |
| PERDIDA | 2,494 | 8.1% |

### Distribution by origen_columna

| Origen | Count |
|--------|-------|
| desconocido | 17,249 |
| ganancia | 5,384 |
| activo | 3,203 |
| pasivo | 2,499 |
| perdida | 2,494 |

**Note:** PATRIMONIO not observed because `ENABLE_DYNAMIC_LAYOUT=False` by default. The resolver needs LayoutDetector to recognize "patrimonio" as a separate column. This is expected and correct.

---

## Diff

```
$ git diff --stat parser_universal.py
 1 file changed, 138 insertions(+), 12 deletions(-)
```

Includes both Sprint 28.2 (LayoutDetector) and Sprint 28.3 (AccountTypeResolver) changes.

AccountTypeResolver-specific additions:
- `ENABLE_ACCOUNT_TYPE_RESOLVER = False` (1 line)
- `tipo_cuenta` field on `CuentaRaw` (1 line)
- `layout_columns` capture in layout detection block (1 line)
- Post-processing block in `ParserPDF.parsear()` (11 lines)
- `parsers/account_type_resolver.py` (139 lines)

---

## Rollback

```bash
# Option A: Restore parser_universal.py only (reverts both Sprint 28.2 and 28.3)
git checkout -- parser_universal.py

# Option B: Delete new files
rm parsers/account_type_resolver.py
rm tests/test_account_type_resolver.py
rm reports/account_type_resolver.md
rm reports/account_type_resolver.json
rm reports/account_type_validation.json
rm reports/run_account_type_validation.py

# Verify
git diff --stat parser_universal.py  # must be empty
python3 -m pytest tests/ -q          # 869 passed, 14 failed
```

**Impact:** Zero. No other modules modified. No data persisted.

---

## Regression Confirmation

| Check | Result |
|-------|--------|
| Account count unchanged? | ✅ Yes — 0/182 docs changed |
| New errors introduced? | ✅ No — 905 pass, same 14 pre-existing fails |
| Classic behavior (flag=False)? | ✅ Yes — flag is False by default |
| Only `parser_universal.py` modified? | ✅ Yes (plus new files) |
| HomologationPipeline modified? | ✅ No — explicitly excluded |

---

## Verdict

**GO.** Component is complete, tested, validated on the full dataset, and safely feature-flagged. Ready for pipeline integration in a future sprint.

---

*Generated by `reports/account_type_resolver.md`*
