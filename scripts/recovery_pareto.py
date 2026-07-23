import pandas as pd
import numpy as np
import re
import unicodedata
import json
from pathlib import Path
from collections import defaultdict
from rapidfuzz import fuzz, process

BASE_DIR = Path('/Users/josealfonsorossel/AI-Projects/homologacion-balances')
GAP_DIR = BASE_DIR / 'reports/classification_gap'
OUTPUT_DIR = BASE_DIR / 'reports/recovery_pareto'
INPUT_FILE = BASE_DIR / 'reports/validation_after/20260707_220654/unclassified.xlsx'
DICT_FILE = BASE_DIR / 'diccionario.json'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_excel(INPUT_FILE)
all_names = df['account_name'].dropna().unique()
TOTAL_ACCOUNTS = len(all_names)
TOTAL_RECORDS = len(df)

freq_map = dict(zip(df['account_name'].value_counts().index, df['account_name'].value_counts().values))
emp_map = df.groupby('account_name')['source_file'].apply(lambda x: x.dropna().nunique() if x.notna().any() else 0).to_dict()
doc_map = df.groupby('account_name')['source_page'].nunique().to_dict()
monto_map = df.groupby('account_name')['classification_amount'].sum().to_dict()

ABBREVIATIONS = {
    'adm': 'administración', 'depr': 'depreciación', 'prov': 'provisión',
    'doc': 'documento', 'cta': 'cuenta', 'ctas': 'cuentas', 'cxc': 'cuentas por cobrar',
    'cxp': 'cuentas por pagar', 'imp': 'impuesto', 'hon': 'honorarios',
    'rrhh': 'recursos humanos', 'inv': 'inventario', 'merc': 'mercaderías',
    'provac': 'provisión acreedores', 'provext': 'proveedores externos',
    'cap': 'capital', 'dep': 'depósito', 'dif': 'diferencia', 'dcto': 'descuento',
    'eq': 'equipo', 'fdo': 'fondo', 'fin': 'financiero', 'gast': 'gasto',
    'gest': 'gestión', 'hab': 'haberes', 'intang': 'intangible', 'mat': 'materiales',
    'mob': 'mobiliario', 'mueb': 'muebles', 'patr': 'patrimonio',
    'ppto': 'presupuesto', 'pto': 'puesto', 'rec': 'recursos',
    'rem': 'remuneración', 'rev': 'revisión', 'rrpp': 'relaciones públicas',
    'soc': 'sociedad', 'sto': 'stock', 'tes': 'tesorería', 'util': 'utilidad',
    'vta': 'venta',
}
PATTERNS = {
    'Gastos':'GASTO','Honorarios':'HONORARIO','Clientes':'CLIENTE','Proveedores':'PROVEEDOR',
    'Existencias':'EXISTENCIA','IVA':'IVA','Activo':'ACTIVO','Pasivo':'PASIVO',
    'Ingresos':'INGRESO','Costos':'COSTO','Banco':'BANCO','Caja':'CAJA',
    'Remuneracion':'REMUNERACION','Capital':'CAPITAL','Depreciacion':'DEPRECIACION',
    'Cuenta':'CUENTA','Cuentas':'CUENTA','Impuesto':'IMPUESTO','Seguro':'SEGURO',
    'Arriendo':'ARRIENDO','Comision':'COMISION','Dividendo':'DIVIDENDO',
    'Interes':'INTERES','Inversion':'INVERSION','Mantenimiento':'MANTENIMIENTO',
    'Publicidad':'PUBLICIDAD','Servicio':'SERVICIO','Sueldo':'SUELDO',
    'Venta':'VENTA','Provision':'PROVISION','Anticipo':'ANTICIPO',
}

def normalize_text(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_parser_artifact(name):
    name = str(name).strip(); lower = name.lower()
    if re.match(r'^(al|del|el)\s+\d+', lower): return True
    if re.match(r'^\d+\s+de\s+', lower): return True
    if re.match(r'^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s', lower): return True
    if 'pagina' in lower or 'pág' in lower or 'pag:' in lower: return True
    if re.match(r'^comuna\s*:', lower): return True
    if re.match(r'^\d{2}-\d{2}-\d{4}', name): return True
    return False

def is_ocr_noise(name):
    name = str(name).strip()
    if sum(1 for c in name if not c.isalnum() and not c.isspace()) / max(len(name),1) > 0.25: return True
    if any(a in name for a in ['|_','|','_','\\\\','//','[',']']): return True
    if re.match(r'^[\d\s,.;:|_\-]+$', name): return True
    if re.match(r'^\d{8,}$', name): return True
    if re.match(r'^\d{1,3}[.,]\d{3}[.,]\d{3}', name): return True
    if re.match(r'^.{0,3}$', name): return True
    tokens = name.split()
    digit_tokens = sum(1 for t in tokens if re.match(r'^[\d.,]+$', t))
    if len(tokens) > 0 and digit_tokens / len(tokens) > 0.6: return True
    return False

with open(DICT_FILE, 'r', encoding='utf-8') as f:
    dict_entries = json.load(f)
dict_names = [e['cuenta_original'] for e in dict_entries]
dict_normalized = {normalize_text(n): n for n in dict_names}
dict_lookup = {e['cuenta_original']: e['codigo_estandar'] for e in dict_entries}

norm_names = {n: normalize_text(n) for n in all_names}

# ── Build account sets per improvement ──
improvements = []

# 1. Normalization + Fuzzy
norm_fuzzy_set = set()
for name in all_names:
    norm = norm_names[name]
    if name in dict_lookup: continue
    if norm in dict_normalized: norm_fuzzy_set.add(name); continue
    best = process.extractOne(norm, list(dict_normalized.keys()), scorer=fuzz.ratio)
    if best and best[1] >= 88: norm_fuzzy_set.add(name)

improvements.append({
    'id': 'NORM-FUZZY', 'tipo': 'Normalización',
    'descripcion': 'Implementar normalización (tildes, mayúsculas, puntuación) + fuzzy matching ≥88%',
    'set': norm_fuzzy_set, 'esfuerzo': 1, 'impacto': 'Alto'
})

# 2. Abbreviations
for abbr, expansion in ABBREVIATIONS.items():
    s = {n for n in all_names if re.search(r'\b' + re.escape(abbr) + r'\b', norm_names[n])}
    if len(s) == 0: continue
    improvements.append({
        'id': f'ABB-{abbr}', 'tipo': 'Abreviatura',
        'descripcion': f'Expandir "{abbr}" → "{expansion}"',
        'set': s, 'esfuerzo': 1,
        'impacto': 'Alto' if len(s) >= 30 else ('Medio' if len(s) >= 10 else 'Bajo')
    })

# 3. Patterns
for pat in PATTERNS:
    pn = normalize_text(pat)
    s = {n for n in all_names if re.search(r'\b' + re.escape(pn) + r'\b', norm_names[n])}
    if len(s) == 0: continue
    improvements.append({
        'id': f'PAT-{pat}', 'tipo': 'Regla',
        'descripcion': f'Regla: cuentas que contienen "{pat}" → asignar código estándar',
        'set': s, 'esfuerzo': 3,
        'impacto': 'Alto' if len(s) >= 80 else ('Medio' if len(s) >= 30 else 'Bajo')
    })

# 4. Synonyms
synonyms_df = pd.read_excel(GAP_DIR / 'synonym_candidates.xlsx')
for _, r in synonyms_df.iterrows():
    s = {str(r['nombre_principal'])}
    v = str(r.get('variantes',''))
    if v and v != 'nan':
        for vn in v.split('|'):
            vn = vn.strip()
            if vn: s.add(vn)
    if len(s) <= 1: continue
    improvements.append({
        'id': f'SIN-{r["grupo"]}', 'tipo': 'Sinónimo',
        'descripcion': f'Normalizar variantes de "{str(r["nombre_principal"])[:50]}"',
        'set': s, 'esfuerzo': 1,
        'impacto': 'Alto' if len(s) >= 5 else ('Medio' if len(s) >= 3 else 'Bajo')
    })

# 5. New dictionary entries
new_dict_set = set()
for name in all_names:
    if is_parser_artifact(name) or is_ocr_noise(name): continue
    if name in dict_lookup: continue
    norm = norm_names[name]
    if norm in dict_normalized: continue
    best = process.extractOne(norm, list(dict_normalized.keys()), scorer=fuzz.ratio)
    if best and best[1] >= 88: continue
    if any(re.search(r'\b' + re.escape(a) + r'\b', norm) for a in ABBREVIATIONS): continue
    new_dict_set.add(name)

improvements.append({
    'id': 'DICT-NEW', 'tipo': 'Diccionario',
    'descripcion': 'Agregar nuevas cuentas al diccionario con código estándar',
    'set': new_dict_set, 'esfuerzo': 5, 'impacto': 'Muy Alto'
})

# 6. OCR
ocr_set = {n for n in all_names if is_ocr_noise(n)}
improvements.append({
    'id': 'OCR-NOISE', 'tipo': 'OCR',
    'descripcion': 'Filtrar/limpiar cuentas con ruido de OCR',
    'set': ocr_set, 'esfuerzo': 4, 'impacto': 'Medio'
})

# 7. Parser
parser_set = {n for n in all_names if is_parser_artifact(n)}
improvements.append({
    'id': 'PARSER-ART', 'tipo': 'Parser',
    'descripcion': 'Filtrar artefactos del parser (fechas, encabezados, páginas)',
    'set': parser_set, 'esfuerzo': 2, 'impacto': 'Bajo'
})

# ── Compute derived fields, sort by ROI ──
for imp in improvements:
    imp['n_cuentas'] = len(imp['set'])
    imp['n_ocurrencias'] = sum(freq_map.get(n, 0) for n in imp['set'])
    imp['empresas'] = sum(emp_map.get(n, 0) for n in imp['set'])
    imp['documentos'] = sum(doc_map.get(n, 0) for n in imp['set'])
    imp['monto'] = sum(monto_map.get(n, 0) for n in imp['set'])
    imp['roi_raw'] = imp['n_ocurrencias'] / imp['esfuerzo']
    imp['impacto_num'] = {'Muy Alto':5,'Alto':4,'Medio':3,'Bajo':2}.get(imp['impacto'], 1)

improvements.sort(key=lambda x: (-x['roi_raw'], -x['impacto_num'], -x['n_cuentas']))

# ── Pareto: walk in order, skip overlaps ──
seen = set()
pareto_list = []
for imp in improvements:
    new = imp['set'] - seen
    if len(new) == 0:
        continue
    n_occ = sum(freq_map.get(n, 0) for n in new)
    n_emp = sum(emp_map.get(n, 0) for n in new)
    n_doc = sum(doc_map.get(n, 0) for n in new)
    pareto_list.append({
        'id': imp['id'],
        'tipo': imp['tipo'],
        'descripcion': imp['descripcion'],
        'cuentas_recuperables': len(new),
        'n_ocurrencias': n_occ,
        'empresas_afectadas': n_emp,
        'documentos_afectados': n_doc,
        'esfuerzo': imp['esfuerzo'],
        'impacto': imp['impacto'],
        'roi': round(n_occ / imp['esfuerzo'], 1),
        'new_set': new,
    })
    seen.update(new)

pareto_df = pd.DataFrame(pareto_list)
FINAL_COVERAGE = len(seen) / TOTAL_ACCOUNTS * 100

cols_out = ['id','tipo','descripcion','cuentas_recuperables','n_ocurrencias',
            'empresas_afectadas','documentos_afectados','esfuerzo','impacto','roi']

# ── 1. recovery_pareto.xlsx ──
pareto_df[cols_out].to_excel(OUTPUT_DIR / 'recovery_pareto.xlsx', index=False)
print(f"1. recovery_pareto.xlsx -> {len(pareto_df)} items")

# ── 2. top50.xlsx ──
n50 = min(50, len(pareto_df))
pareto_df.head(n50)[cols_out].to_excel(OUTPUT_DIR / 'top50.xlsx', index=False)
print(f"2. top50.xlsx -> {n50} items")

# ── 3. top20.xlsx ──
pareto_df.head(20)[cols_out].to_excel(OUTPUT_DIR / 'top20.xlsx', index=False)
print(f"3. top20.xlsx -> 20 items")

# ── 4. cumulative_gain.xlsx ──
gain_points = [1, 5, 10, 20, 30, 40, 50]
gain_rows = []
cum = set()
prev_cov = 0
for idx in range(len(pareto_list)):
    cum.update(pareto_list[idx]['new_set'])
    rank = idx + 1
    if rank in gain_points:
        cov = len(cum) / TOTAL_ACCOUNTS * 100
        marginal = cov - prev_cov
        gain_rows.append({
            'top_n': rank,
            'cobertura_acumulada': round(cov, 1),
            'incremento_marginal': round(marginal, 1),
            'cuentas_acumuladas': len(cum),
            'roi_acumulado': round(sum(pareto_list[i]['roi'] for i in range(rank)), 1),
        })
        prev_cov = cov

# Also add final coverage if there are more items beyond gain_points
if len(pareto_list) > max(gain_points) if gain_points else False:
    final_gp = {
        'top_n': len(pareto_list),
        'cobertura_acumulada': round(len(cum)/TOTAL_ACCOUNTS*100, 1),
        'incremento_marginal': round(prev_cov - len(cum)/TOTAL_ACCOUNTS*100, 1) if False else round(len(cum)/TOTAL_ACCOUNTS*100 - prev_cov, 1),
        'cuentas_acumuladas': len(cum),
        'roi_acumulado': round(sum(pareto_list[i]['roi'] for i in range(len(pareto_list))), 1),
    }
    # Only add if not already at this point
    if not any(g['top_n'] == len(pareto_list) for g in gain_rows):
        gain_rows.append(final_gp)

gain_df = pd.DataFrame(gain_rows)
gain_df.to_excel(OUTPUT_DIR / 'cumulative_gain.xlsx', index=False)
print(f"4. cumulative_gain.xlsx -> {len(gain_df)} rows")
for _, r in gain_df.iterrows():
    print(f"   Top {r['top_n']}: {r['cobertura_acumulada']}% (Δ+{r['incremento_marginal']}%)")

# ── 5. implementation_order.xlsx ──
time_map = {1:'0.5 días',2:'1 día',3:'2 días',4:'5 días',5:'15+ días'}
dep_map = {'Normalización':'Ninguna','Abreviatura':'Normalización','Sinónimo':'Normalización',
           'Regla':'Abreviaturas + Normalización','Diccionario':'Reglas + Abreviaturas',
           'OCR':'Parser','Parser':'Ninguna'}
order_rows = []
cum2 = set()
for idx, item in enumerate(pareto_list):
    cum2.update(item['new_set'])
    order_rows.append({
        'prioridad': idx+1, 'id': item['id'], 'descripcion': item['descripcion'],
        'tipo': item['tipo'], 'dependencias': dep_map.get(item['tipo'],'Ninguna'),
        'tiempo_estimado': time_map.get(item['esfuerzo'],'1 día'),
        'cuentas_recuperables': item['cuentas_recuperables'],
        'cobertura_individual': round(item['cuentas_recuperables']/TOTAL_ACCOUNTS*100,1),
        'cobertura_acumulada': round(len(cum2)/TOTAL_ACCOUNTS*100,1),
    })

order_df = pd.DataFrame(order_rows)
order_df.to_excel(OUTPUT_DIR / 'implementation_order.xlsx', index=False)
print(f"5. implementation_order.xlsx -> {len(order_df)} items")

# ── 6. pareto_report.md ──
# Compute cumulative sets at key cutoffs
cum5 = set(); cum10 = set(); cum20 = set(); cum50 = set()
max_idx = min(50, len(pareto_list))
for idx in range(max_idx):
    s = pareto_list[idx]['new_set']
    if idx < 5: cum5.update(s)
    if idx < 10: cum10.update(s)
    if idx < 20: cum20.update(s)
    cum50.update(s)

if len(pareto_list) < 50:
    cum50 = cum20

cov5 = len(cum5)/TOTAL_ACCOUNTS*100
cov10 = len(cum10)/TOTAL_ACCOUNTS*100
cov20 = len(cum20)/TOTAL_ACCOUNTS*100
cov50 = len(cum50)/TOTAL_ACCOUNTS*100

# Auto vs manual
auto_types = {'Normalización','Abreviatura','Sinónimo','Parser'}
manual_types = {'Regla','Diccionario','OCR'}
auto_accts = set()
manual_accts = set()
for item in pareto_list:
    if item['tipo'] in auto_types:
        auto_accts.update(item['new_set'])
    if item['tipo'] in manual_types:
        manual_accts.update(item['new_set'])

report = f"""# Pareto Recovery Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Total cuentas sin clasificar | {TOTAL_ACCOUNTS:,} |
| Mejoras evaluadas | {len(improvements)} |
| Mejoras con beneficio neto (no solapado) | {len(pareto_list)} |
| Cobertura final (sin solapamiento) | {FINAL_COVERAGE:.1f}% |
| Cuentas recuperables únicas | {len(seen):,} |

## 1. ¿Cuáles son las 20 mejoras que más cobertura recuperan?

| # | ID | Tipo | Descripción | Cuentas nuevas | Esfuerzo | ROI |
|---|-----|------|-------------|---------------|----------|-----|
"""

for idx, item in enumerate(pareto_list[:20], 1):
    desc = item['descripcion'][:65]
    report += f"| {idx} | {item['id']} | {item['tipo']} | {desc} | {item['cuentas_recuperables']} | {item['esfuerzo']} | {item['roi']} |\n"

report += f"""
## 2. ¿Cuántas cuentas recupera cada una de las top 20?

"""
for idx, item in enumerate(pareto_list[:20], 1):
    report += f"- **{idx}. {item['id']}** ({item['tipo']}): {item['descripcion'][:60]} → **{item['cuentas_recuperables']} cuentas**, esfuerzo {item['esfuerzo']}, ROI {item['roi']}\n"

report += f"""
## 3. Cobertura acumulada después de implementar

| Hito | Cuentas acumuladas | Cobertura | Incremento marginal |
|------|-------------------|-----------|-------------------|
"""

prev = 0
for _, gr in gain_df.iterrows():
    mg = gr['cobertura_acumulada'] - prev
    report += f"| Top {gr['top_n']} | {gr['cuentas_acumuladas']} | {gr['cobertura_acumulada']}% | +{mg:.1f}% |\n"
    prev = gr['cobertura_acumulada']

report += f"""
**Cobertura total final**: {FINAL_COVERAGE:.1f}%

## 4. ¿Qué porcentaje del beneficio proviene de las primeras 20?

- Beneficio total alcanzable: **{FINAL_COVERAGE:.1f}%** ({len(seen):,} cuentas)
- Beneficio solo con top 20: **{cov20:.1f}%** ({len(cum20):,} cuentas)
- Las primeras 20 representan **{cov20/FINAL_COVERAGE*100:.1f}%** del beneficio total

## 5. ¿Cuáles requieren contador?

| ID | Tipo | Descripción |
|----|------|-------------|
"""

for item in pareto_list:
    if item['tipo'] in {'Regla','Diccionario'}:
        report += f"| {item['id']} | {item['tipo']} | {item['descripcion'][:60]} |\n"

report += f"""
**Total manual (requiere contador)**: {len(manual_accts):,} cuentas ({len(manual_accts)/TOTAL_ACCOUNTS*100:.1f}%)

## 6. ¿Cuáles pueden automatizarse sin intervención humana?

| ID | Tipo | Descripción |
|----|------|-------------|
"""

for item in pareto_list:
    if item['tipo'] in auto_types:
        report += f"| {item['id']} | {item['tipo']} | {item['descripcion'][:60]} |\n"

report += f"""
**Total automático (sin contador)**: {len(auto_accts):,} cuentas ({len(auto_accts)/TOTAL_ACCOUNTS*100:.1f}%)

## 7. Distribución por tipo de mejora

| Tipo | Mejoras | Cuentas únicas | % del total |
|------|---------|---------------|------------|
"""

for t in ['Normalización','Abreviatura','Sinónimo','Regla','Diccionario','OCR','Parser']:
    sub = [item for item in pareto_list if item['tipo'] == t]
    if not sub: continue
    sub_set = set()
    for item in sub: sub_set.update(item['new_set'])
    report += f"| {t} | {len(sub)} | {len(sub_set)} | {len(sub_set)/TOTAL_ACCOUNTS*100:.1f}% |\n"

report += f"""
## 8. Orden de implementación recomendado (top 10)

| # | ID | Tipo | Descripción | Cuentas | Esfuerzo |
|---|-----|------|-------------|---------|----------|
"""

for idx, item in enumerate(pareto_list[:10], 1):
    report += f"| {idx} | {item['id']} | {item['tipo']} | {item['descripcion'][:55]} | {item['cuentas_recuperables']} | {item['esfuerzo']} |\n"

report += f"""
## 9. Conclusión

**Ley de Pareto aplicada a la clasificación de cuentas**:

- **{20/len(improvements)*100:.1f}%** de las mejoras (top 20) recuperan **{cov20/FINAL_COVERAGE*100:.1f}%** de las cuentas recuperables
- Las primeras **5 mejoras** recuperan **{cov5:.1f}%** del total ({cov5/FINAL_COVERAGE*100:.1f}% del beneficio)
- Las primeras **10 mejoras** recuperan **{cov10:.1f}%** del total ({cov10/FINAL_COVERAGE*100:.1f}% del beneficio)

**Estrategia óptima**:

1. **Sprint inmediato**: Normalización + Fuzzy matching (esfuerzo 1, 0 dependencias)
2. **Sprint 1**: Expandir abreviaturas de alto impacto (cta, dep, mat, rev, inv - esfuerzo 1 c/u)
3. **Sprint 2**: Reglas por patrón (Gastos*, Banco*, Cuentas*, Venta* - requieren código contable)
4. **Sprint 3**: Sinónimos + abreviaturas restantes + filtro parser
5. **Sprint 4**: Diccionario masivo + limpieza OCR

**Impacto esperado**:
- Automático (sin contador): {len(auto_accts):,} cuentas ({len(auto_accts)/TOTAL_ACCOUNTS*100:.1f}%)
- Requiere contador: {len(manual_accts):,} cuentas ({len(manual_accts)/TOTAL_ACCOUNTS*100:.1f}%)
- **Total**: {len(seen):,} cuentas ({FINAL_COVERAGE:.1f}%)
"""

(OUTPUT_DIR / 'pareto_report.md').write_text(report, encoding='utf-8')
print(f"\n6. pareto_report.md -> {len(report)} chars")
print(f"\n{'='*60}")
print(f"ALL OUTPUTS IN: {OUTPUT_DIR}")
print(f"Cobertura final sin solapamiento: {FINAL_COVERAGE:.1f}%")
print(f"{'='*60}")
