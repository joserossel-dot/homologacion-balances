# Release Governance Report

**Release ID**: REL_20260722_231446
**Timestamp**: 2026-07-22T23:14:47.039343+00:00
**Git Commit**: ab7b81d Update parser_universal.py
**Git Branch**: HEAD
**Decision**: `BLOCKED`
**Execution Time**: 0.06s

## 1. Test Results

- **0** tests executed
- **0** passed
- **0** failed

## 2. Stage Execution

| Stage | Status | Duration | Errors | Warnings |
|-------|--------|----------|--------|----------|
| ✅ Deployment Decision | PASS | 0.00s | 0 | 0 |

**Slowest stage**: Deployment Decision (0.00s)

## 3. Gate Results

- ❌ **Coverage Drift**: Coverage dropped 5pp
- ❌ **UNKNOWN Growth**: UNKNOWN grew by 1000

## 4. Deployment Decision

### ❌ BLOCKED

Deployment blocked due to gate failures:
- **DRIFT_GATE** (FAIL): Coverage dropped 5pp
  - Report: reports/quality_monitoring/quality_monitoring.md
- **UNKNOWN_GATE** (FAIL): UNKNOWN grew by 1000
  - Report: reports/quality_monitoring/quality_monitoring.md

**Action required**: Fix the issues above and re-run the release check.

## 5. Quality Metrics

- Coverage: N/A%
- Classified: N/A
- UNKNOWN: N/A
- Parser Confidence: N/A
- Accuracy: N/A

## 6. Drift Metrics

- Coverage drop: 0pp
- UNKNOWN growth: 0 (0%)
- Accuracy drop: 0

## 7. Knowledge Evolution

- Classifications before: N/A
- Classifications after: N/A
- New classifications: N/A
- Coverage before: N/A%
- Coverage after: N/A%

## 8. Alerts

- Critical alerts: 1
- High alerts: 1

- 🔴 **CRITICAL**: Coverage dropped 5pp
- 🟡 **HIGH**: UNKNOWN grew by 1000

## 9. Recommendations

1. **Fix gate failures**: Address each failed gate before re-running release check.
2. **Review evidence**: Check the referenced reports for each failure.
3. **Re-run**: Execute `python scripts/release_check.py` after fixes.