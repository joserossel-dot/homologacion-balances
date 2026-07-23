import pandas as pd
import numpy as np
from pathlib import Path
import json

BASE_DIR = Path('/Users/josealfonsorossel/AI-Projects/homologacion-balances')
GAP_DIR = BASE_DIR / 'reports/classification_gap'
OUTPUT_DIR = BASE_DIR / 'reports/recovery_matrix'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILE = BASE_DIR / 'reports/validation_after/20260707_220654/unclassified.xlsx'
df_raw = pd.read_excel(INPUT_FILE)
TOTAL_ACCOUNTS = df_raw['account_name'].nunique()
TOTAL_RECORDS = len(df_raw)
TOTAL_AMOUNT = df_raw['classification_amount'].sum()

top_accounts = pd.read_excel(GAP_DIR / 'top_accounts.xlsx')
synonyms = pd.read_excel(GAP_DIR / 'synonym_candidates.xlsx')
patterns = pd.read_excel(GAP_DIR / 'pattern_candidates.xlsx')
dictionary_matches = pd.read_excel(GAP_DIR / 'dictionary_matches.xlsx')
abbreviations = pd.read_excel(GAP_DIR / 'abbreviations.xlsx')

freq_map = dict(zip(df_raw['account_name'].value_counts().index.astype(str),
                     df_raw['account_name'].value_counts().values))
empresas_map = df_raw.groupby('account_name')['source_file'].apply(
    lambda x: x.dropna().nunique() if x.notna().any() else 0
).to_dict()
montos_map = df_raw.groupby('account_name')['classification_amount'].sum().to_dict()

match_type_map = dict(zip(dictionary_matches['cuenta'], dictionary_matches['tipo_match']))

rows = []

# ── Synonyms ──
for _, r in synonyms.iterrows():
    principal = str(r['nombre_principal'])
    variants_str = str(r.get('variantes', ''))
    all_names = [principal] + ([v.strip() for v in variants_str.split('|') if v.strip()] if variants_str and variants_str != 'nan' else [])
    n_accts = len(all_names)
    total_occ = sum(freq_map.get(n, 0) for n in all_names)
    total_emp = sum(empresas_map.get(n, 0) for n in all_names)
    total_mto = sum(montos_map.get(n, 0) for n in all_names)
    rows.append({
        'grupo': f'SIN-{r["grupo"]}',
        'tipo': 'Sinónimo',
        'nombre_principal': principal,
        'n_cuentas_distintas': n_accts,
        'n_ocurrencias': total_occ,
        'empresas_afectadas': total_emp,
        'total_montos': total_mto,
        'esfuerzo': 2,
        'impacto_esperado': 'Alto' if total_occ >= 20 else ('Medio' if total_occ >= 10 else 'Bajo'),
        'roi': round(total_occ / 2, 1),
        'modo': 'Automático (normalización)',
        'dependencia': 'Ninguna'
    })

# ── Patterns ──
for _, r in patterns.iterrows():
    rows.append({
        'grupo': f'PAT-{r["patron"]}',
        'tipo': 'Regla',
        'nombre_principal': r['patron'],
        'n_cuentas_distintas': r['n_cuentas'],
        'n_ocurrencias': r['frecuencia'],
        'empresas_afectadas': 0,
        'total_montos': 0,
        'esfuerzo': 3,
        'impacto_esperado': 'Alto' if r['frecuencia'] >= 100 else ('Medio' if r['frecuencia'] >= 40 else 'Bajo'),
        'roi': round(r['frecuencia'] / 3, 1),
        'modo': 'Regla programática',
        'dependencia': 'Revisión contable para asignar código'
    })

# ── Abbreviations ──
for _, r in abbreviations.iterrows():
    rows.append({
        'grupo': f'ABB-{r["abreviatura"]}',
        'tipo': 'Abreviatura',
        'nombre_principal': f'{r["abreviatura"]} → {r["expansion_sugerida"]}',
        'n_cuentas_distintas': r['n_cuentas'],
        'n_ocurrencias': r['frecuencia'],
        'empresas_afectadas': 0,
        'total_montos': 0,
        'esfuerzo': 1,
        'impacto_esperado': 'Alto' if r['frecuencia'] >= 50 else ('Medio' if r['frecuencia'] >= 20 else 'Bajo'),
        'roi': round(r['frecuencia'] / 1, 1),
        'modo': 'Automático (tabla de expansión)',
        'dependencia': 'Ninguna'
    })

# ── Bulk: Dictionary expansion ──
new_dict_accts = dictionary_matches[dictionary_matches['tipo_match'] == 'NEW_ACCOUNT']
new_dict_count = new_dict_accts['cuenta'].nunique()
new_dict_occ = sum(freq_map.get(n, 0) for n in new_dict_accts['cuenta'])
new_dict_emp = sum(empresas_map.get(n, 0) for n in new_dict_accts['cuenta'])
new_dict_mto = sum(montos_map.get(n, 0) for n in new_dict_accts['cuenta'])
rows.append({
    'grupo': 'DICT-NEW',
    'tipo': 'Diccionario',
    'nombre_principal': 'Nuevas entradas en diccionario',
    'n_cuentas_distintas': new_dict_count,
    'n_ocurrencias': new_dict_occ,
    'empresas_afectadas': new_dict_emp,
    'total_montos': new_dict_mto,
    'esfuerzo': 5,
    'impacto_esperado': 'Muy Alto',
    'roi': round(new_dict_occ / 5, 1),
    'modo': 'Manual (revisión contable)',
    'dependencia': 'Contador para asignar código estándar'
})

# ── Bulk: OCR noise ──
ocr_accts = dictionary_matches[dictionary_matches['tipo_match'] == 'OCR_NOISE']
ocr_count = ocr_accts['cuenta'].nunique()
ocr_occ = sum(freq_map.get(n, 0) for n in ocr_accts['cuenta'])
ocr_emp = sum(empresas_map.get(n, 0) for n in ocr_accts['cuenta'])
ocr_mto = sum(montos_map.get(n, 0) for n in ocr_accts['cuenta'])
rows.append({
    'grupo': 'OCR-NOISE',
    'tipo': 'OCR',
    'nombre_principal': 'Filtrar/limpiar ruido de OCR',
    'n_cuentas_distintas': ocr_count,
    'n_ocurrencias': ocr_occ,
    'empresas_afectadas': ocr_emp,
    'total_montos': ocr_mto,
    'esfuerzo': 4,
    'impacto_esperado': 'Medio',
    'roi': round(ocr_occ / 4, 1),
    'modo': 'Híbrido (filtro automático + mejora fuente)',
    'dependencia': 'Proveedor OCR / formato PDF origen'
})

# ── Bulk: Parser artifacts ──
parser_accts = dictionary_matches[dictionary_matches['tipo_match'] == 'PARSER_ARTIFACT']
parser_count = parser_accts['cuenta'].nunique()
parser_occ = sum(freq_map.get(n, 0) for n in parser_accts['cuenta'])
parser_emp = sum(empresas_map.get(n, 0) for n in parser_accts['cuenta'])
parser_mto = sum(montos_map.get(n, 0) for n in parser_accts['cuenta'])
rows.append({
    'grupo': 'PARSER-ART',
    'tipo': 'Parser',
    'nombre_principal': 'Filtrar artefactos del parser',
    'n_cuentas_distintas': parser_count,
    'n_ocurrencias': parser_occ,
    'empresas_afectadas': parser_emp,
    'total_montos': parser_mto,
    'esfuerzo': 2,
    'impacto_esperado': 'Bajo',
    'roi': round(parser_occ / 2, 1),
    'modo': 'Automático (reglas de filtro)',
    'dependencia': 'Ninguna'
})

# ── Bulk: Normalization ──
norm_accts = dictionary_matches[dictionary_matches['tipo_match'].isin(['NORMALIZED_MATCH', 'FUZZY_MATCH'])]
norm_count = norm_accts['cuenta'].nunique()
norm_occ = sum(freq_map.get(n, 0) for n in norm_accts['cuenta'])
norm_emp = sum(empresas_map.get(n, 0) for n in norm_accts['cuenta'])
norm_mto = sum(montos_map.get(n, 0) for n in norm_accts['cuenta'])
rows.append({
    'grupo': 'NORM-FUZZY',
    'tipo': 'Normalización',
    'nombre_principal': 'Normalización + Fuzzy Matching',
    'n_cuentas_distintas': norm_count,
    'n_ocurrencias': norm_occ,
    'empresas_afectadas': norm_emp,
    'total_montos': norm_mto,
    'esfuerzo': 1,
    'impacto_esperado': 'Alto',
    'roi': round(norm_occ / 1, 1),
    'modo': 'Automático (mejora de pipeline)',
    'dependencia': 'Ninguna'
})

matrix = pd.DataFrame(rows)
matrix = matrix.sort_values('roi', ascending=False)

# Effort (already set) + Impact numeric for sorting
impact_map = {'Muy Alto': 5, 'Alto': 4, 'Medio': 3, 'Bajo': 2, 'Muy Bajo': 1}
matrix['impacto_num'] = matrix['impacto_esperado'].map(impact_map)
matrix['prioridad_score'] = (matrix['impacto_num'] * matrix['n_cuentas_distintas']) / matrix['esfuerzo']
matrix = matrix.sort_values('prioridad_score', ascending=False)

matrix.to_excel(OUTPUT_DIR / 'recovery_matrix.xlsx', index=False)
print(f"1. recovery_matrix.xlsx -> {len(matrix)} rows")

# ── Priority Backlog ──
backlog = matrix.copy()
backlog = backlog.sort_values(['esfuerzo', 'prioridad_score'], ascending=[True, False])
backlog['prioridad'] = range(1, len(backlog) + 1)
backlog_cols = ['prioridad', 'grupo', 'tipo', 'nombre_principal', 'n_cuentas_distintas',
                'n_ocurrencias', 'empresas_afectadas', 'esfuerzo', 'impacto_esperado',
                'roi', 'modo', 'dependencia']
backlog.to_excel(OUTPUT_DIR / 'priority_backlog.xlsx', index=False, columns=backlog_cols)
print(f"2. priority_backlog.xlsx -> {len(backlog)} items prioritized")

# ── Top 100 Recoverable ──
top100 = matrix.head(100).copy()
top100['prioridad'] = range(1, 101)
top100.to_excel(OUTPUT_DIR / 'top_100_recoverable.xlsx', index=False,
                columns=backlog_cols)
print(f"3. top_100_recoverable.xlsx -> {len(top100)} items")

# ── Sprint Plan ──
# Split into 4 sprints with balanced effort
# Sort by ROI
sprint_items = matrix.sort_values('prioridad_score', ascending=False).copy()

total_effort = sprint_items['esfuerzo'].sum()
effort_per_sprint = total_effort / 4

sprint_items['sprint'] = 0
sprint_items['esfuerzo_acum'] = sprint_items['esfuerzo'].cumsum()

sprint_items.loc[sprint_items['esfuerzo_acum'] <= effort_per_sprint, 'sprint'] = 1
mask = sprint_items['sprint'] == 0
sprint_items.loc[mask & (sprint_items['esfuerzo_acum'] <= effort_per_sprint * 2), 'sprint'] = 2
mask = sprint_items['sprint'] == 0
sprint_items.loc[mask & (sprint_items['esfuerzo_acum'] <= effort_per_sprint * 3), 'sprint'] = 3
sprint_items.loc[sprint_items['sprint'] == 0, 'sprint'] = 4

# Manual override: ensure normalization + fuzzy + top abbreviations are sprint 1
# Put DICT-NEW in sprint 4 (highest effort)
sprint_items.loc[sprint_items['grupo'] == 'NORM-FUZZY', 'sprint'] = 1
for abbr in abbreviations.head(10)['abreviatura']:
    mask = sprint_items['grupo'] == f'ABB-{abbr}'
    sprint_items.loc[mask, 'sprint'] = 1
sprint_items.loc[sprint_items['grupo'] == 'DICT-NEW', 'sprint'] = 4
sprint_items.loc[sprint_items['grupo'] == 'OCR-NOISE', 'sprint'] = 4
sprint_items.loc[sprint_items['grupo'] == 'PARSER-ART', 'sprint'] = 3

items_s1 = sprint_items[sprint_items['sprint'] == 1]
items_s2 = sprint_items[sprint_items['sprint'] == 2]
items_s3 = sprint_items[sprint_items['sprint'] == 3]
items_s4 = sprint_items[sprint_items['sprint'] == 4]

sprint_summary_rows = []
cumulative_count = 0

for s_num, s_items in [(1, items_s1), (2, items_s2), (3, items_s3), (4, items_s4)]:
    s_effort = s_items['esfuerzo'].sum()
    s_impact_accts = s_items['n_cuentas_distintas'].sum()
    s_impact_occ = s_items['n_ocurrencias'].sum()
    cumulative_count += s_impact_accts
    s_coverage = cumulative_count / TOTAL_ACCOUNTS * 100
    sprint_summary_rows.append({
        'sprint': f'Sprint {s_num}',
        'n_items': len(s_items),
        'esfuerzo_total': s_effort,
        'cuentas_recuperables': s_impact_accts,
        'ocurrencias_recuperables': s_impact_occ,
        'cobertura_individual': f'{s_impact_accts/TOTAL_ACCOUNTS*100:.1f}%',
        'cobertura_acumulada': f'{s_coverage:.1f}%',
        'tipos_principales': ' | '.join(s_items['tipo'].value_counts().index[:3])
    })

sprint_summary = pd.DataFrame(sprint_summary_rows)

# Add sprint assignment to each item for detail view
sprint_detail_rows = []
for s_num, s_items in [(1, items_s1), (2, items_s2), (3, items_s3), (4, items_s4)]:
    for _, r in s_items.iterrows():
        sprint_detail_rows.append({
            'sprint': f'Sprint {s_num}',
            'prioridad': 0,
            'grupo': r['grupo'],
            'tipo': r['tipo'],
            'nombre_principal': r['nombre_principal'],
            'n_cuentas_distintas': r['n_cuentas_distintas'],
            'n_ocurrencias': r['n_ocurrencias'],
            'esfuerzo': r['esfuerzo'],
            'impacto_esperado': r['impacto_esperado'],
            'modo': r['modo']
        })

sprint_detail = pd.DataFrame(sprint_detail_rows)
# Assign priority within each sprint
for s in ['Sprint 1', 'Sprint 2', 'Sprint 3', 'Sprint 4']:
    mask = sprint_detail['sprint'] == s
    sprint_detail.loc[mask, 'prioridad'] = range(1, mask.sum() + 1)

with pd.ExcelWriter(OUTPUT_DIR / 'sprint_plan.xlsx') as writer:
    sprint_summary.to_excel(writer, sheet_name='Resumen', index=False)
    sprint_detail.to_excel(writer, sheet_name='Detalle', index=False)
print(f"4. sprint_plan.xlsx -> {len(sprint_detail)} items in 4 sprints")

# ── Recovery Report ──
top20 = matrix.head(20)
top50 = matrix.head(50)
all_items = matrix

top20_accts = top20['n_cuentas_distintas'].sum()
top20_occ = top20['n_ocurrencias'].sum()
top20_cov = top20_accts / TOTAL_ACCOUNTS * 100

top50_accts = top50['n_cuentas_distintas'].sum()
top50_occ = top50['n_ocurrencias'].sum()
top50_cov = top50_accts / TOTAL_ACCOUNTS * 100

all_accts = all_items['n_cuentas_distintas'].sum()
all_occ = all_items['n_ocurrencias'].sum()
all_cov = all_accts / TOTAL_ACCOUNTS * 100

# Overlap correction: some accounts appear in multiple categories
# Estimate unique recoverable accounts
synonym_accts = set()
for _, r in synonyms.iterrows():
    p = str(r['nombre_principal'])
    v = str(r.get('variantes', ''))
    synonym_accts.add(p)
    if v and v != 'nan':
        for vn in v.split('|'):
            synonym_accts.add(vn.strip())

pattern_accts_total = int(patterns['n_cuentas'].sum())
abbrev_accts = set(dictionary_matches[dictionary_matches['tipo_match'] == 'ABBREVIATION']['cuenta'])
new_dict_accts = set(dictionary_matches[dictionary_matches['tipo_match'] == 'NEW_ACCOUNT']['cuenta'])
norm_accts_set = set(dictionary_matches[dictionary_matches['tipo_match'].isin(['NORMALIZED_MATCH', 'FUZZY_MATCH'])]['cuenta'])
ocr_accts_set = set(dictionary_matches[dictionary_matches['tipo_match'] == 'OCR_NOISE']['cuenta'])
parser_accts_set = set(dictionary_matches[dictionary_matches['tipo_match'] == 'PARSER_ARTIFACT']['cuenta'])

# Count unique accounts by high-level category
cat_accounting = new_dict_accts | abbrev_accts
cat_parser = parser_accts_set | ocr_accts_set
cat_normalization = norm_accts_set | synonym_accts

unique_accounting_only = cat_accounting - cat_parser - cat_normalization
unique_parser_only = cat_parser - cat_accounting - cat_normalization
unique_norm_only = cat_normalization - cat_parser - cat_accounting

report = f"""# Recovery Opportunity Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas sin clasificar | {TOTAL_ACCOUNTS:,} |
| Total registros sin clasificar | {TOTAL_RECORDS:,} |
| Oportunidades de mejora identificadas | {len(matrix)} |
| Cobertura potencial (suma simple) | {all_cov:.1f}% |
| Cobertura potencial (única estimada) | ~{min(int(all_accts), TOTAL_ACCOUNTS):,} cuentas |

## 1. ¿Cuáles son las 20 mejoras con mayor retorno?

| # | Grupo | Tipo | Cuentas | Ocurrencias | Esfuerzo | ROI |
|---|-------|------|---------|------------|----------|-----|
"""

for idx, (_, r) in enumerate(top20.iterrows(), 1):
    report += f"| {idx} | {r['grupo']} | {r['tipo']} | {r['n_cuentas_distintas']} | {r['n_ocurrencias']} | {r['esfuerzo']} | {r['roi']} |\n"

report += f"""
## 2. ¿Cuánto aumentaría la cobertura si solo se implementan las top 20?

- Cuentas recuperables: **{top20_accts:,}**
- Ocurrencias recuperables: **{top20_occ:,}**
- Cobertura sobre cuentas totales: **{top20_cov:.1f}%**
- Cobertura sobre ocurrencias totales: **{top20_occ/TOTAL_RECORDS*100:.1f}%**

## 3. ¿Cuánto si se implementan las primeras 50?

- Cuentas recuperables: **{top50_accts:,}**
- Ocurrencias recuperables: **{top50_occ:,}**
- Cobertura sobre cuentas totales: **{top50_cov:.1f}%**
- Cobertura sobre ocurrencias totales: **{top50_occ/TOTAL_RECORDS*100:.1f}%**

## 4. ¿Cuánto si se implementan todas?

- Cuentas recuperables: **{all_accts:,}**
- Ocurrencias recuperables: **{all_occ:,}**
- Cobertura sobre cuentas totales: **{all_cov:.1f}%**
- Cobertura sobre ocurrencias totales: **{all_occ/TOTAL_RECORDS*100:.1f}%**

Nota: Las cuentas pueden contarse en múltiples categorías. La cobertura real única es menor.

## 5. ¿Qué porcentaje requiere intervención humana?

| Categoría | Cuentas | % del total | Intervención |
|-----------|---------|------------|-------------|
| Nuevas entradas en diccionario | {new_dict_count:,} | {new_dict_count/TOTAL_ACCOUNTS*100:.1f}% | Manual — contador asigna código |
| Abreviaturas con ambigüedad | ~{len(abbreviations[abbreviations['confianza']=='media'])} | ~{len(abbreviations[abbreviations['confianza']=='media'])/TOTAL_ACCOUNTS*100:.2f}% | Revisión de expansión correcta |
| Patrones sin código asignado | {len(patterns)} | {len(patterns)/TOTAL_ACCOUNTS*100:.2f}% | Contador define regla de asignación |

**Total con intervención humana**: ~{new_dict_count + len(patterns)} cuentas ({(new_dict_count + len(patterns))/TOTAL_ACCOUNTS*100:.1f}%)

**Sin intervención humana** (automático): ~{int(all_accts - new_dict_count - len(patterns))} cuentas ({(all_accts - new_dict_count - len(patterns))/TOTAL_ACCOUNTS*100:.1f}%)

## 6. ¿Cuánto trabajo corresponde realmente al parser?

| Componente | Cuentas | % del total | Esfuerzo estimado |
|-----------|---------|------------|------------------|
| Artefactos del parser (filtrar) | {parser_count} | {parser_count/TOTAL_ACCOUNTS*100:.1f}% | Bajo (días) |
| Ruido de OCR (limpiar) | {ocr_count} | {ocr_count/TOTAL_ACCOUNTS*100:.1f}% | Medio-Alto (depende fuente) |
| Total atribuible al parser/OCR | {parser_count + ocr_count} | {(parser_count+ocr_count)/TOTAL_ACCOUNTS*100:.1f}% | — |

## 7. ¿Cuánto corresponde al conocimiento contable?

| Componente | Cuentas | % del total | Descripción |
|-----------|---------|------------|-------------|
| Nuevas entradas en diccionario | {new_dict_count:,} | {new_dict_count/TOTAL_ACCOUNTS*100:.1f}% | Cuentas válidas no mapeadas a código estándar |
| Reglas por patrón | {len(patterns)} | {len(patterns)/TOTAL_ACCOUNTS*100:.2f}% | Requiere definir qué código asignar a cada patrón |
| Normalización (automático contable) | {norm_count} | {norm_count/TOTAL_ACCOUNTS*100:.1f}% | Ya existen en diccionario, solo normalizar |
| Sinónimos (automático contable) | {len(synonym_accts)} | {len(synonym_accts)/TOTAL_ACCOUNTS*100:.1f}% | Variantes de cuentas ya conocidas |

**Total atribuible al conocimiento contable**: ~{new_dict_count + len(patterns)} cuentas ({(new_dict_count+len(patterns))/TOTAL_ACCOUNTS*100:.1f}%) requieren criterio contable.

## 8. Sprint Plan

| Sprint | Items | Esfuerzo | Cuentas | Cobertura individual | Cobertura acumulada | Tipos principales |
|--------|-------|----------|---------|---------------------|-------------------|-------------------|
"""

for _, r in sprint_summary.iterrows():
    report += f"| {r['sprint']} | {r['n_items']} | {r['esfuerzo_total']} | {r['cuentas_recuperables']} | {r['cobertura_individual']} | {r['cobertura_acumulada']} | {r['tipos_principales']} |\n"

report += f"""
### Sprint 1 — Quick Wins (Alta prioridad)
- Normalización + Fuzzy Matching
- Abreviaturas de alto impacto (cta, dep, mat, rev, inv, soc, ctas)
- Principales sinónimos

### Sprint 2 — Reglas y Abreviaturas
- Patrones de alto impacto (Gastos *, Banco *, Capital *, Ventas *)
- Abreviaturas restantes
- Sinónimos adicionales

### Sprint 3 — Patrones restantes y Parser
- Patrones de menor impacto
- Filtrar artefactos del parser
- Sinónimos restantes

### Sprint 4 — Diccionario y OCR
- Nuevas entradas en diccionario (revisión manual)
- Limpieza de ruido OCR

## 9. Conclusión

**Mayor retorno inmediato**: Normalización + Fuzzy matching (esfuerzo 1, recupera {norm_count} cuentas).

**Mayor impacto absoluto**: Nuevas entradas en diccionario ({new_dict_count} cuentas, {new_dict_count/TOTAL_ACCOUNTS*100:.1f}%) pero requiere revisión manual.

**Porcentaje automático sin intervención humana**: ~{int(norm_count + len(synonym_accts) + ocr_count + parser_count + len(patterns))} cuentas.

**Porcentaje que requiere contador**: ~{new_dict_count/TOTAL_ACCOUNTS*100:.1f}% (diccionario) + {len(patterns)/TOTAL_ACCOUNTS*100:.2f}% (reglas).

**Estrategia recomendada**:
1. Sprint 1: Implementar normalización + fuzzy matching + abreviaturas (días, cero intervención humana)
2. Sprint 2: Agregar reglas por patrón con revisión contable ligera
3. Sprint 3: Limpiar artefactos del parser y sinónimos restantes
4. Sprint 4: Abordar diccionario nuevo con revisión manual masiva + mejora OCR
"""

(OUTPUT_DIR / 'recovery_report.md').write_text(report, encoding='utf-8')
print(f"5. recovery_report.md -> {len(report)} chars")
print(f"\n{'='*60}")
print(f"ALL OUTPUTS IN: {OUTPUT_DIR}")
print(f"{'='*60}")
