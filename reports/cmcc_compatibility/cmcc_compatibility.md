# CMCC Compatibility Report

**Generated:** 2026-07-10 14:14:42 UTC

## Summary

| Metric | Value |
|---|---|
| Total Checks | 40 |
| Passed | 40 |
| Failed | 0 |
| Compatible | Yes |

## Detailed Results

| Component | Check | Status |
|---|---|---|
| Feature Flags | ENABLE_CMCC exists | PASS |
| Feature Flags | ENABLE_CMCC_SHADOW exists | PASS |
| Feature Flags | ENABLE_CMCC_PRODUCTION exists | PASS |
| Feature Flags | ENABLE_CMCC_ROLLBACK exists | PASS |
| Feature Flags | ENABLE_CMCC defaults to False | PASS |
| Feature Flags | ENABLE_CMCC_ROLLBACK forces all flags off | PASS |
| Feature Flags | from_env() parses env vars correctly | PASS |
| Feature Flags | to_dict() serializes all fields | PASS |
| Decision Trace | DecisionTrace.cmcc_match exists | PASS |
| Decision Trace | DecisionTrace.cmcc_match_type exists | PASS |
| Decision Trace | DecisionTrace.cmcc_variant exists | PASS |
| Decision Trace | DecisionTrace.cmcc_score exists | PASS |
| Decision Trace | DecisionTrace.shadow_classification exists | PASS |
| Decision Trace | DecisionTrace.shadow_confidence exists | PASS |
| Decision Trace | DecisionCode.D007 exists (Shadow CMCC) | PASS |
| Decision Trace | TraceStage.CMCC exists | PASS |
| Decision Trace | TraceBuilder maps cmcc_nombre | PASS |
| Decision Trace | TraceBuilder maps cmcc_variante | PASS |
| Decision Trace | TraceBuilder maps cmcc_sinonimo | PASS |
| Decision Trace | TraceBuilder maps cmcc_abreviatura | PASS |
| Decision Trace | TraceBuilder maps cmcc_none | PASS |
| Decision Trace | TraceBuilder builds traces for CMCC accounts | PASS |
| Release Pipeline | GateEngine imports | PASS |
| Release Pipeline | PipelineRunner imports | PASS |
| Release Pipeline | ReleaseContext imports | PASS |
| Release Pipeline | GateEngine.cmcc_gate exists | PASS |
| Release Pipeline | ReleaseContext.dictionary_hash (CMCC hash) | PASS |
| Module Imports | pipeline.features imports | PASS |
| Module Imports | pipeline.cmcc_classifier imports | PASS |
| Module Imports | pipeline.homologation_pipeline imports | PASS |
| Module Imports | explainability imports | PASS |
| Module Imports | explainability.decision_trace imports | PASS |
| Module Imports | explainability.trace_builder imports | PASS |
| Module Imports | explainability.trace_report imports | PASS |
| Module Imports | explainability.trace_exporter imports | PASS |
| Module Imports | explainability.enums imports | PASS |
| Module Imports | shadow.shadow_logger imports | PASS |
| Pipeline Integration | HomologationPipeline instantiates CMCCClassifier | PASS |
| Pipeline Integration | HomologationPipeline accepts CMCCFeatureFlags | PASS |
| Pipeline Integration | CMCCFeatureFlags.default() used when none provided | PASS |

---
*Compatibility verified. No production code was modified.*