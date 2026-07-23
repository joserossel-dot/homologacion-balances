# Homologación de Balances — Resumen del Proyecto

## Goal
Build complete knowledge discovery, proposal generation, review packaging, evidence preservation, pattern recognition, and dictionary audit layers for the homologation pipeline — without modifying existing classification logic.

## Constraints & Preferences
- Do NOT modify pipeline/, semantic/, learning/, knowledge/, gold_standard/, validation/
- Do NOT write real rules, modify scores, or change classification
- All new modules must remain decoupled and not modify existing project files
- All existing tests must continue passing
- Pattern Engine must operate in shadow mode (learning/semantic engine unchanged)
- Dictionary audit is read-only — no migration, no import changes, no file renames

## Progress
### Done
- **FASE 12B — Semantic Shadow Evaluation**: 186 files processed (1,259s). 163 semantic hits (1.5%), 98 accounts detected by semantic but missed by pipeline, 0 discrepancies, 8/10 rules used. Reports in `reports/semantic_shadow/`
- **FASE 13A — Knowledge Discovery Engine**: 5 modules in `knowledge/`. 8,762 unclassified accounts → 1,168 clusters (rapidfuzz token_set_ratio ≥ 70%). 534 rule candidates, 393 synonym groups, 927 ranked recommendations
- **FASE 13B — Knowledge Generator**: 4 modules. Generated 533 semantic rule fragments, 2,598 dictionary entries, 185 gold standard entries, 29,622 test lines. All outputs text-only, not incorporated
- **FASE 14A — Review Package Generator**: `review/` package (5 modules). 8-sheet Excel (2.0 MB): 9,031 pending rows, professional formatting with conditional coloring and dropdowns. 32 tests (27 fast, 5 slow)
- **FASE 14B — Account Evidence Layer**: `evidence/` package (6 modules). `AccountEvidence` dataclass with 40+ fields, `MonetaryAmounts` restored, context windows (3 before/after), backward-compatible serialization. Converts 10,672 shadow accounts to evidence objects. Reports in `reports/evidence/`
- **FASE 15A — Accounting Pattern Engine (APE)**: 8 modules in `patterns/`. 15 `AccountingPattern` families with compiled regex, `PatternNormalizer` (accent removal, CxC/CxP expansion, punctuation→space), `PatternMatcher` (single/best/all matching), `PatternEngine` (orchestration over 10,672 accounts), `PatternBuilder` (programmatic creation/validation), `PatternReport` (md + xlsx × 3 + json). **Coverage: 1,467/8,762 (16.74%)** unclassified accounts resolved by patterns alone. Top families: BANCOS (265), CUENTAS_POR_COBRAR (240), CUENTAS_POR_PAGAR (216). Reports in `reports/patterns/`
- **FASE 1A — Dictionary Audit**: `tools/dictionary_audit.py` + 4 reports in `reports/dictionary/`. Inventoried 13 references across 5 source files. Compared 3 dictionaries (826/781/712 entries). Found **0 conflicts** (same name → same code across all 3), **45 entries exclusive to diccionario.json** (all validacion_humana/lote), **69 entries removed in optimizado** (66 validacion_humana + 3 excluido_analista). **0 internal name duplicates**, **0 empty entries**, **16 suspicious names** (special chars), **3 `__EXCLUIR__` entries**. Reports: `dictionary_audit.md`, `dictionary_statistics.json`, `dictionary_duplicates.xlsx`, `dictionary_conflicts.xlsx`
- **FASE 1A.1 — Dictionary Validation**: `tools/validate_dictionary_audit.py`. Confirmed 712 exact name+code matches across all 3 files. Found 2 intra-dictionary consistency issues (ANC.01 vs ER.07 for "Depreciación Activos en Leasing"; AC.09 vs AC.05 for "Activos biológicos corrientes") — both exist IDENTICALLY in all 3 files, so **0 cross-file migration conflicts**. Detected 45 normalized-equivalent pairs (same normalized name + same code). Classified 3 `__EXCLUIR__` entries as parser blacklist candidates. Analyzed 16 suspicious names: 10 medium risk (dólar/grado/N°), 3 high risk (2 with `__EXCLUIR__` codes, 1 with `> <` handled by normalizer). Generated `reports/dictionary/validation_report.md`

### In Progress
- (none)

### Blocked
- (none)

## Key Decisions
- Pattern Engine uses regex matching against normalized (uppercase, accent-free, punctuation-replaced) names exclusively — no fuzzy, no ML, no learning. Each family has a single compiled regex with keyword_forbidden exclusion. Patterns avoid zero-length lookahead matches (tokens_found extraction requires non-zero match range)
- `PatternNormalizer` replaces ALL punctuation with spaces (not removal) so "Dep.Ac." → "DEP AC" preserves token separation. Abbreviation expansions (CxC → CUENTAS POR COBRAR) happen AFTER uppercasing, BEFORE punctuation replacement. Leading numeric-only tokens are stripped
- 15 families were defined with priority (10-90) and confidence (75%-92%). Highest priority: DEPRECIACION_ACUMULADA (priority 10, conf 0.92). Lowest: CAPITAL (priority 90, conf 0.85)
- Pattern coverage (16.74%) is sufficient for shadow-mode validation but not yet production-ready — 7,295 unclassified accounts remain unmatched
- Dictionary canonical source is **diccionario.json** (826 entries, human-updated via Streamlit). diccionario_optimizado.json (712 entries, used by pipeline) is outdated and loses 114 entries. **Migration is safe**: 0 cross-file conflicts, 0 internal duplicates, 0 empty entries across all 3 files
- `__EXCLUIR__` entries (3 found: "Ejercicio Local 2022 Página:", "Intereses Créditos Bancarios...", "Al 31 de diciembre del") should become a blacklist filter in the pipeline rather than dictionary entries — 1 line of code
- 2 intra-dictionary consistency issues exist identically in ALL files: "Depreciación Activos en Leasing" coded as both ANC.01 and ER.07 (orthographic error DEPRECIACÍON); "activos biologicos corrientes" coded as both AC.05 and AC.09. These are NOT migration blockers but should be reviewed for correctness
- Validation confirmed 0 actual migration blockers: exact-name comparison shows all 712 shared entries have identical codes; normalized-name comparison reveals only pre-existing intra-file issues

## Next Steps
1. **Migrate pipeline** to use `diccionario.json` as canonical dictionary — update paths in 4 files: `pipeline/homologation_pipeline.py:40`, `src/db_repository.py:70`, `evaluation/homologation_benchmark.py:17,91`, `cargar_datos.py:51`
2. Add `__EXCLUIR__` filter in `pipeline/homologation_pipeline.py:_load_dictionary()` to skip entries with `codigo_estandar == "__EXCLUIR__"`
3. Normalize 16 suspicious names in `diccionario.json` (remove $, °, N°, > <, leading zeros)
4. Resolve 2 intra-dictionary code conflicts (ANC.01 vs ER.07, AC.09 vs AC.05)
5. Increase Pattern Engine coverage by adding more families or refining existing regexes
6. Generate Monte Carlo simulation for coverage impact of adding each pattern family

## Critical Context
- shadow_data.json data loss: `source_file=""` (100%), `source_page=0` (100%), `source_group` = only "validacion"/"edge_cases", `classification_amount` scalar only (MonetaryAmounts lost), `account_code` empty for all 8,762 unclassified
- 23.3% of account names have extraction issues (2,259 numeric-prefixed, 293 colons, 412 ERP codes)
- Evidence layer solves all these at parser-output level but cannot recover already-lost data from shadow_data.json
- Pattern Engine runs in shadow mode: no changes to pipeline, learning, semantic, or knowledge engines
- AMORTIZACION_DEL_EJERCICIO family has 0 matches in real data — either too specific or no such accounts exist in current dataset
- DEPRECIACION_DEL_EJERCICIO matched only 7 accounts (all unclassified) — validates the family catches real pipeline gaps
- 1,467 unclassified accounts resolved by patterns out of 8,762 (16.74%) — baseline for future coverage improvements
- All 3 dictionaries have 0 empty entries, 0 internal name duplicates, 0 cross-file code conflicts
- diccionario.json has 45 entries not in actualizado.json (removed in Streamlit download) + 69 entries not in optimizado.json (removed in optimization pass, all validacion_humana)
- Validacion_humana entries (69 total removed in optimizado) were likely excluded due to lower confidence, not errors — their codes match the canonical entries exactly
- The 3 `__EXCLUIR__` entries in diccionario.json are all from "excluido_analista" source and have 0 matches in optimizado.json
- 2 pairs of entries normalize to same form but have different codes: "Depreciación Activos en Leasing" (ANC.01) vs "DEPRECIACÍON ACTIVOS EN LEASING" (ER.07); "Activos biológicos corrientes" (AC.09) vs "activos biologicos corrientes" (AC.05). Both pairs exist identically in ALL 3 dictionary files, confirming they are pre-existing consistency issues, not migration conflicts

## Relevant Files
- `patterns/pattern_catalog.py`: 15 AccountingPattern families with compiled regex
- `patterns/pattern_normalizer.py`: accent/punctuation removal + CxC/CxP expansion + leading-code stripping
- `patterns/pattern_matcher.py`: PatternMatch dataclass, single/best/all matching, forbidden keyword check
- `patterns/pattern_engine.py`: orchestration — load shadow data, analyze all accounts, compute coverage
- `patterns/pattern_builder.py`: build/validate/test patterns programmatically from dict
- `patterns/pattern_report.py`: 5 report formats (md + xlsx × 3 + json) in `reports/patterns/`
- `patterns/run_pattern_analysis.py`: CLI runner — `python3 patterns/run_pattern_analysis.py`
- `test_patterns.py`: 92 tests (all passing), covers each family's examples + negative examples
- `reports/patterns/`: pattern_coverage.md, pattern_statistics.xlsx, pattern_unmatched.xlsx, pattern_examples.xlsx, pattern_analysis.json
- `tools/dictionary_audit.py`: full audit — loads 3 JSON files, detects duplicates/conflicts/suspicious/invalid, generates 4 reports
- `tools/validate_dictionary_audit.py`: deep validation — normalized comparison, __EXCLUIR__ classification, suspicious name analysis, migration readiness assessment
- `test_dictionary_audit.py`: 27 tests covering loading, analysis, comparison, inventory, reports, real-data integration
- `reports/dictionary/`: dictionary_audit.md (387 lines), dictionary_statistics.json, dictionary_duplicates.xlsx, dictionary_conflicts.xlsx, validation_report.md
- `diccionario.json`: 826 entries — canonical (updated by Streamlit), 9 sources, 49 codes
- `diccionario_actualizado.json`: 781 entries — Streamlit download snapshot, 8 sources, 49 codes
- `diccionario_optimizado.json`: 712 entries — used by pipeline, 6 sources (no validacion_humana), 46 codes
- `pipeline/homologation_pipeline.py:40`: loads `diccionario_optimizado.json` — target for migration
- `src/db_repository.py:70`: fallback reader of `diccionario_optimizado.json` — target for migration
- `evaluation/homologation_benchmark.py:17,91`: default path `diccionario_optimizado.json` — target for migration
- `cargar_datos.py:51`: loads `diccionario_optimizado.json` for PostgreSQL upsert — target for migration
- `app_validacion.py:70,1111,1267,1294`: reads/writes `diccionario.json` — already canonical
