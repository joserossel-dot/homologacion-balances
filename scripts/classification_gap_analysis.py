import pandas as pd
import numpy as np
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from rapidfuzz import fuzz, process

BASE_DIR = Path('/Users/josealfonsorossel/AI-Projects/homologacion-balances')
INPUT_FILE = BASE_DIR / 'reports/validation_after/20260707_220654/unclassified.xlsx'
OUTPUT_DIR = BASE_DIR / 'reports/classification_gap'
DICT_FILE = BASE_DIR / 'diccionario.json'

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_excel(INPUT_FILE)
print(f"Loaded {len(df)} rows, {df['account_name'].nunique()} unique accounts")

STOPWORDS = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'con',
             'para', 'por', 'al', 'en', 'un', 'una', 'a', 'su', 'e'}

ABBREVIATIONS = {
    'adm': 'administración',
    'depr': 'depreciación',
    'prov': 'provisión',
    'doc': 'documento',
    'cta': 'cuenta',
    'ctas': 'cuentas',
    'cxc': 'cuentas por cobrar',
    'cxp': 'cuentas por pagar',
    'imp': 'impuesto',
    'hon': 'honorarios',
    'rrhh': 'recursos humanos',
    'inv': 'inventario',
    'merc': 'mercaderías',
    'provac': 'provisión acreedores',
    'provext': 'proveedores externos',
    'cap': 'capital',
    'dep': 'depósito',
    'dif': 'diferencia',
    'dcto': 'descuento',
    'eq': 'equipo',
    'fdo': 'fondo',
    'fin': 'financiero',
    'gast': 'gasto',
    'gest': 'gestión',
    'hab': 'haberes',
    'intang': 'intangible',
    'mat': 'materiales',
    'mob': 'mobiliario',
    'mueb': 'muebles',
    'patr': 'patrimonio',
    'ppto': 'presupuesto',
    'pto': 'puesto',
    'rec': 'recursos',
    'rem': 'remuneración',
    'rev': 'revisión',
    'rrpp': 'relaciones públicas',
    'soc': 'sociedad',
    'sto': 'stock',
    'tes': 'tesorería',
    'util': 'utilidad',
    'vta': 'venta',
}

PATTERNS = {
    'Gastos': 'GASTO',
    'Honorarios': 'HONORARIO',
    'Clientes': 'CLIENTE',
    'Proveedores': 'PROVEEDOR',
    'Existencias': 'EXISTENCIA',
    'IVA': 'IVA',
    'Activo': 'ACTIVO',
    'Pasivo': 'PASIVO',
    'Ingresos': 'INGRESO',
    'Costos': 'COSTO',
    'Banco': 'BANCO',
    'Caja': 'CAJA',
    'Remuneracion': 'REMUNERACION',
    'Capital': 'CAPITAL',
    'Depreciacion': 'DEPRECIACION',
    'Cuenta': 'CUENTA',
    'Cuentas': 'CUENTA',
    'Impuesto': 'IMPUESTO',
    'Seguro': 'SEGURO',
    'Arriendo': 'ARRIENDO',
    'Comision': 'COMISION',
    'Dividendo': 'DIVIDENDO',
    'Interes': 'INTERES',
    'Inversion': 'INVERSION',
    'Mantenimiento': 'MANTENIMIENTO',
    'Publicidad': 'PUBLICIDAD',
    'Servicio': 'SERVICIO',
    'Sueldo': 'SUELDO',
    'Venta': 'VENTA',
    'Provision': 'PROVISION',
    'Anticipo': 'ANTICIPO',
}

def normalize_text(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_light(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize(text):
    return [t for t in text.split() if t not in STOPWORDS and len(t) > 1]

def has_amount_embedded(name):
    name = str(name)
    if re.search(r'\d+[.,]\d{3}', name):
        return True
    if re.search(r'\d{6,}', name):
        return True
    return False

def is_parser_artifact(name):
    name = str(name).strip()
    lower = name.lower()
    if re.match(r'^(al|del|el)\s+\d+', lower):
        return True
    if re.match(r'^\d+\s+de\s+', lower):
        return True
    months = r'^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s'
    if re.match(months, lower):
        return True
    if 'pagina' in lower or 'pág' in lower or 'pag:' in lower:
        return True
    if re.match(r'^comuna\s*:', lower):
        return True
    if re.match(r'^\d{2}-\d{2}-\d{4}', name):
        return True
    if re.match(r'^[a-z]+\s+\d+[.,]?\d*$', lower) and len(name) < 30:
        return False
    return False

def is_ocr_noise(name):
    name = str(name).strip()
    artifacts = ['|_', '|', '_', '\\\\', '//', '[', ']']
    ratio_symbols = sum(1 for c in name if not c.isalnum() and not c.isspace()) / max(len(name), 1)
    if ratio_symbols > 0.25:
        return True
    if any(a in name for a in artifacts):
        return True
    if re.match(r'^[\d\s,.;:|_\-]+$', name):
        return True
    if re.match(r'^\d{8,}$', name):
        return True
    if re.match(r'^\d{1,3}[.,]\d{3}[.,]\d{3}', name):
        return True
    if re.match(r'^.{0,3}$', name):
        return True
    tokens = name.split()
    digit_tokens = sum(1 for t in tokens if re.match(r'^[\d.,]+$', t))
    if len(tokens) > 0 and digit_tokens / len(tokens) > 0.6:
        return True
    return False

def is_valid_account_name(name):
    if is_parser_artifact(name):
        return False
    if is_ocr_noise(name):
        return False
    return True

all_names = df['account_name'].dropna().unique()
print(f"Total unique account names: {len(all_names)}")

valid_names = [n for n in all_names if is_valid_account_name(n)]
invalid_names = [n for n in all_names if not is_valid_account_name(n)]
print(f"Valid accounts: {len(valid_names)}, Invalid (parser/OCR noise): {len(invalid_names)}")

with open(DICT_FILE, 'r', encoding='utf-8') as f:
    dict_entries = json.load(f)

dict_names = [e['cuenta_original'] for e in dict_entries]
dict_normalized = {normalize_text(n): n for n in dict_names}
dict_lookup = {e['cuenta_original']: e['codigo_estandar'] for e in dict_entries}
dict_norm_to_code = {normalize_text(e['cuenta_original']): e['codigo_estandar'] for e in dict_entries}

freq_map = df['account_name'].value_counts().to_dict()
empresas_map = df.groupby('account_name')['source_file'].apply(lambda x: x.dropna().nunique() if x.notna().any() else 0).to_dict()
montos_map = df.groupby('account_name')['classification_amount'].sum().to_dict()

# ──────────────────────────────────────────────
# 1. TOP ACCOUNTS
# ──────────────────────────────────────────────
accounts = pd.DataFrame([{
    'cuenta': n,
    'frecuencia': freq_map.get(n, 0),
    'empresas_distintas': empresas_map.get(n, 0),
    'documentos_distintos': df[df['account_name'] == n]['source_page'].nunique(),
    'total_montos': montos_map.get(n, 0),
    'longitud_nombre': len(str(n))
} for n in all_names]).sort_values('frecuencia', ascending=False)

accounts.to_excel(OUTPUT_DIR / 'top_accounts.xlsx', index=False)
print(f"\n1. top_accounts.xlsx -> {len(accounts)} accounts")

# ──────────────────────────────────────────────
# 2. TOP TOKENS
# ──────────────────────────────────────────────
token_counter = Counter()
token_accounts = defaultdict(set)

for name in all_names:
    norm = normalize_text(name)
    tokens = tokenize(norm)
    for t in set(tokens):
        token_counter[t] += 1
        token_accounts[t].add(name)

top_tokens = pd.DataFrame([
    {'token': t, 'frecuencia': token_counter[t], 'n_cuentas_distintas': len(token_accounts[t])}
    for t in token_counter
]).sort_values('frecuencia', ascending=False).head(200)

top_tokens.to_excel(OUTPUT_DIR / 'top_tokens.xlsx', index=False)
print(f"2. top_tokens.xlsx -> {len(top_tokens)} tokens")

# ──────────────────────────────────────────────
# 3. ABBREVIATIONS
# ──────────────────────────────────────────────
abbr_results = []
for name in valid_names:
    norm = normalize_text(name)
    for abbr, expansion in ABBREVIATIONS.items():
        if re.search(r'\b' + re.escape(abbr) + r'\b', norm):
            abbr_results.append({
                'abreviatura': abbr,
                'expansion_sugerida': expansion,
                'cuenta': name,
                'frecuencia_cuenta': freq_map.get(name, 0)
            })

abbr_df = pd.DataFrame(abbr_results)
if len(abbr_df) > 0:
    abbr_summary = abbr_df.groupby(['abreviatura', 'expansion_sugerida']).agg(
        frecuencia=('frecuencia_cuenta', 'sum'),
        n_cuentas=('cuenta', 'nunique')
    ).reset_index().sort_values('frecuencia', ascending=False)
    conf_map = {True: 'alta', False: 'media'}
    abbr_summary['confianza'] = abbr_summary['n_cuentas'].apply(lambda x: 'alta' if x >= 5 else ('media' if x >= 2 else 'baja'))
else:
    abbr_summary = pd.DataFrame(columns=['abreviatura', 'expansion_sugerida', 'frecuencia', 'n_cuentas', 'confianza'])

abbr_summary.to_excel(OUTPUT_DIR / 'abbreviations.xlsx', index=False)
abbreviation_accounts = abbr_df['cuenta'].nunique() if len(abbr_df) > 0 else 0
print(f"3. abbreviations.xlsx -> {len(abbr_summary)} abbreviations, {abbreviation_accounts} accounts")

# ──────────────────────────────────────────────
# 4. SYNONYM CANDIDATES (improved)
# ──────────────────────────────────────────────
valid_deduped = list(dict.fromkeys(valid_names))

def get_tokens_set(name):
    return set(tokenize(normalize_text(name)))

def synonym_score(name1, name2):
    n1 = normalize_text(name1)
    n2 = normalize_text(name2)
    ratio = fuzz.ratio(n1, n2)
    t1 = get_tokens_set(name1)
    t2 = get_tokens_set(name2)
    if len(t1) == 0 or len(t2) == 0:
        return 0
    jaccard = len(t1 & t2) / len(t1 | t2)
    token_overlap = len(t1 & t2) / min(len(t1), len(t2))
    combined = ratio * 0.4 + jaccard * 100 * 0.3 + token_overlap * 100 * 0.3
    return combined

# Efficient grouping: group by first token to avoid O(n^2)
buckets = defaultdict(list)
for idx, name in enumerate(valid_deduped):
    norm = normalize_text(name)
    tokens = tokenize(norm)
    key = tokens[0] if tokens else name
    buckets[key].append(idx)

synonym_groups = []
assigned = set()

for key, bucket_idxs in buckets.items():
    for i_idx in range(len(bucket_idxs)):
        i = bucket_idxs[i_idx]
        if i in assigned:
            continue
        group_idxs = [i]
        assigned.add(i)
        for j_idx in range(i_idx + 1, len(bucket_idxs)):
            j = bucket_idxs[j_idx]
            if j in assigned:
                continue
            score = synonym_score(valid_deduped[i], valid_deduped[j])
            if score >= 85:
                group_idxs.append(j)
                assigned.add(j)
        if len(group_idxs) > 1:
            group_names = [valid_deduped[idx] for idx in group_idxs]
            group_freqs = [freq_map.get(n, 0) for n in group_names]
            total_freq = sum(group_freqs)
            synonym_groups.append({
                'grupo': len(synonym_groups) + 1,
                'nombre_principal': group_names[0],
                'variantes': ' | '.join(group_names[1:]),
                'frecuencia': total_freq,
                'n_variantes_detectadas': len(group_names) - 1,
                'confianza': 'alta' if len(group_names) <= 5 else 'media'
            })

synonym_df = pd.DataFrame(synonym_groups).sort_values('frecuencia', ascending=False)
synonym_df.to_excel(OUTPUT_DIR / 'synonym_candidates.xlsx', index=False)
synonym_accounts = len(set())
for g in synonym_groups:
    synonym_accounts += 1 + len(g['variantes'].split(' | ')) - 1
print(f"4. synonym_candidates.xlsx -> {len(synonym_df)} groups, {synonym_accounts} accounts")

# ──────────────────────────────────────────────
# 5. DICTIONARY MATCHES
# ──────────────────────────────────────────────
dict_matches = []
for name in all_names:
    if name in dict_lookup:
        dict_matches.append({'cuenta': name, 'tipo_match': 'EXACT_MATCH', 'codigo_estandar': dict_lookup[name], 'confianza': 1.0})
        continue
    norm = normalize_text(name)
    if norm in dict_normalized:
        dict_matches.append({'cuenta': name, 'tipo_match': 'NORMALIZED_MATCH', 'codigo_estandar': dict_lookup[dict_normalized[norm]], 'confianza': 0.95})
        continue
    best = process.extractOne(norm, list(dict_normalized.keys()), scorer=fuzz.ratio)
    if best and best[1] >= 88:
        matched_dict_name = dict_normalized[best[0]]
        dict_matches.append({'cuenta': name, 'tipo_match': 'FUZZY_MATCH', 'codigo_estandar': dict_lookup[matched_dict_name], 'confianza': round(best[1] / 100, 2)})
        continue
    if not is_valid_account_name(name):
        if is_ocr_noise(name):
            dict_matches.append({'cuenta': name, 'tipo_match': 'OCR_NOISE', 'codigo_estandar': '', 'confianza': 0.0})
        else:
            dict_matches.append({'cuenta': name, 'tipo_match': 'PARSER_ARTIFACT', 'codigo_estandar': '', 'confianza': 0.0})
        continue
    abbr_match_code = None
    norm_lower = normalize_text(name)
    for abbr, expansion in ABBREVIATIONS.items():
        if re.search(r'\b' + re.escape(abbr) + r'\b', norm_lower):
            for dn in dict_normalized:
                if expansion.split('/')[0] in dn or (len(abbr) > 2 and abbr in dn):
                    abbr_match_code = dict_lookup[dict_normalized[dn]]
                    break
            if abbr_match_code:
                break
    if abbr_match_code:
        dict_matches.append({'cuenta': name, 'tipo_match': 'ABBREVIATION', 'codigo_estandar': abbr_match_code, 'confianza': 0.7})
        continue
    dict_matches.append({'cuenta': name, 'tipo_match': 'NEW_ACCOUNT', 'codigo_estandar': '', 'confianza': 0.0})

dm_df = pd.DataFrame(dict_matches)
dm_df.to_excel(OUTPUT_DIR / 'dictionary_matches.xlsx', index=False)
print(f"5. dictionary_matches.xlsx -> {len(dm_df)} accounts")
match_counts = dm_df['tipo_match'].value_counts()
for k, v in match_counts.items():
    print(f"   {k}: {v} ({v/len(all_names)*100:.1f}%)")

# ──────────────────────────────────────────────
# 6. PATTERN CANDIDATES
# ──────────────────────────────────────────────
pattern_results = []
for name in all_names:
    if not is_valid_account_name(name):
        continue
    norm = normalize_text(name)
    for pat_label, pat_category in PATTERNS.items():
        pat_clean = normalize_text(pat_label)
        if re.search(r'\b' + re.escape(pat_clean) + r'\b', norm):
            pattern_results.append({
                'patron': f'{pat_label} *',
                'categoria': pat_category,
                'cuenta': name,
                'frecuencia_cuenta': freq_map.get(name, 0)
            })

pat_df = pd.DataFrame(pattern_results)
if len(pat_df) > 0:
    pat_summary = pat_df.groupby(['patron', 'categoria']).agg(
        frecuencia=('frecuencia_cuenta', 'sum'),
        n_cuentas=('cuenta', 'nunique')
    ).reset_index().sort_values('frecuencia', ascending=False)
else:
    pat_summary = pd.DataFrame(columns=['patron', 'categoria', 'frecuencia', 'n_cuentas'])

pat_summary.to_excel(OUTPUT_DIR / 'pattern_candidates.xlsx', index=False)
pattern_accounts = pat_df['cuenta'].nunique() if len(pat_df) > 0 else 0
print(f"6. pattern_candidates.xlsx -> {len(pat_summary)} patterns, {pattern_accounts} accounts")

# ──────────────────────────────────────────────
# 7. IMPACT ESTIMATION (no double counting)
# ──────────────────────────────────────────────
ocr_noise_accounts = dm_df[dm_df['tipo_match'] == 'OCR_NOISE']['cuenta'].nunique()
parser_artifact_accounts = dm_df[dm_df['tipo_match'] == 'PARSER_ARTIFACT']['cuenta'].nunique()
new_dict_accounts = dm_df[dm_df['tipo_match'] == 'NEW_ACCOUNT']['cuenta'].nunique()
abbrev_accounts = dm_df[dm_df['tipo_match'] == 'ABBREVIATION']['cuenta'].nunique()
fuzzy_accounts = dm_df[dm_df['tipo_match'] == 'FUZZY_MATCH']['cuenta'].nunique()
norm_accounts = dm_df[dm_df['tipo_match'] == 'NORMALIZED_MATCH']['cuenta'].nunique()

synonym_accts_unique = len(set(
    n for g in synonym_groups
    for n in [g['nombre_principal']] + g['variantes'].split(' | ')
))

pattern_accts_unique = pattern_accounts

normalization_total = norm_accounts + fuzzy_accounts

# Priority 1 (normalization + synonyms) - MUST avoid double counting between them
p1_synonym = synonym_accts_unique
p1_norm = normalization_total
p1_overlap = len(set(
    n for g in synonym_groups
    for n in [g['nombre_principal']] + g['variantes'].split(' | ')
) & set(dm_df[dm_df['tipo_match'].isin(['FUZZY_MATCH', 'NORMALIZED_MATCH'])]['cuenta']))
p1_total = p1_synonym + p1_norm - p1_overlap

p2_abbrev = abbrev_accounts
p2_overlap_abbrev_syn = len(set(
    n for g in synonym_groups
    for n in [g['nombre_principal']] + g['variantes'].split(' | ')
) & set(dm_df[dm_df['tipo_match'] == 'ABBREVIATION']['cuenta']))
p2_overlap_abbrev_norm = len(set(dm_df[dm_df['tipo_match'] == 'ABBREVIATION']['cuenta']) & set(
    dm_df[dm_df['tipo_match'].isin(['FUZZY_MATCH', 'NORMALIZED_MATCH'])]['cuenta']))

p2_patterns = pattern_accts_unique
p2_overlap_pat_syn = len(set(
    n for g in synonym_groups
    for n in [g['nombre_principal']] + g['variantes'].split(' | ')
) & set(pat_df['cuenta'].unique()))
p2_overlap_pat_norm = len(set(dm_df[dm_df['tipo_match'].isin(['FUZZY_MATCH', 'NORMALIZED_MATCH'])]['cuenta']) & set(pat_df['cuenta'].unique()))
p2_overlap_pat_abbrev = len(set(dm_df[dm_df['tipo_match'] == 'ABBREVIATION']['cuenta']) & set(pat_df['cuenta'].unique()))

p3_dict = new_dict_accounts

impact = pd.DataFrame([
    {'accion': 'Normalización (fuzzy + normalized)',
     'cuentas_recuperables': p1_norm,
     'porcentaje': round(p1_norm / len(all_names) * 100, 1),
     'esfuerzo': 'Bajo',
     'prioridad': 1},
    {'accion': 'Sinónimos',
     'cuentas_recuperables': p1_synonym,
     'porcentaje': round(p1_synonym / len(all_names) * 100, 1),
     'esfuerzo': 'Bajo',
     'prioridad': 1},
    {'accion': 'Abreviaturas',
     'cuentas_recuperables': p2_abbrev,
     'porcentaje': round(p2_abbrev / len(all_names) * 100, 1),
     'esfuerzo': 'Medio',
     'prioridad': 2},
    {'accion': 'Reglas (patrones detectables)',
     'cuentas_recuperables': p2_patterns,
     'porcentaje': round(p2_patterns / len(all_names) * 100, 1),
     'esfuerzo': 'Medio',
     'prioridad': 2},
    {'accion': 'Nuevas entradas en diccionario',
     'cuentas_recuperables': p3_dict,
     'porcentaje': round(p3_dict / len(all_names) * 100, 1),
     'esfuerzo': 'Alto (validación manual)',
     'prioridad': 3},
    {'accion': 'Filtrar artefactos del parser',
     'cuentas_recuperables': parser_artifact_accounts,
     'porcentaje': round(parser_artifact_accounts / len(all_names) * 100, 1),
     'esfuerzo': 'Bajo',
     'prioridad': 3},
    {'accion': 'Mejorar OCR / limpiar ruido',
     'cuentas_recuperables': ocr_noise_accounts,
     'porcentaje': round(ocr_noise_accounts / len(all_names) * 100, 1),
     'esfuerzo': 'Alto (depende de fuente)',
     'prioridad': 3},
])

impact = impact.sort_values('prioridad')
impact.to_excel(OUTPUT_DIR / 'impact_estimation.xlsx', index=False)
print(f"\n7. impact_estimation.xlsx")
print(impact.to_string(index=False))

# ──────────────────────────────────────────────
# 8. GAP REPORT
# ──────────────────────────────────────────────
top_100 = accounts[accounts['cuenta'].isin(valid_names)].head(100)
p1_invalid = parser_artifact_accounts + ocr_noise_accounts

valid_but_unmatched = new_dict_accounts + abbrev_accounts + fuzzy_accounts + norm_accounts

report = f"""# Classification Gap Report — Análisis de Cuentas No Clasificadas

## Resumen Ejecutivo

Se analizaron **{len(all_names):,} cuentas distintas** no clasificadas (de {len(df):,} registros totales).

| Métrica | Valor |
|---------|-------|
| Total registros sin clasificar | {len(df):,} |
| Cuentas distintas sin clasificar | {len(all_names):,} |
| Cuentas válidas (no son ruido) | {len(valid_names):,} |
| Cuentas inválidas (parser/OCR) | {len(invalid_names):,} |
| Monto total no clasificado | ${df['classification_amount'].sum():,.0f} |
| Entradas en diccionario actual | {len(dict_entries)} |
| Códigos estándar disponibles | {len(set(e['codigo_estandar'] for e in dict_entries))} |

## 1. ¿Cuántas cuentas distintas siguen sin clasificar?

**{len(all_names):,} cuentas distintas** están sin clasificar.

De ellas, **{len(valid_names):,} ({len(valid_names)/len(all_names)*100:.1f}%)** son cuentas válidas que debieran clasificarse.
Las restantes **{len(invalid_names):,} ({len(invalid_names)/len(all_names)*100:.1f}%)** son artefactos del parser o ruido de OCR.

## 2. Top 100 cuentas más frecuentes (válidas)

Las 100 cuentas válidas más frecuentes representan **{top_100['frecuencia'].sum():,} ocurrencias** ({top_100['frecuencia'].sum()/len(df)*100:.1f}% del total de registros).

| # | Cuenta | Frecuencia | Empresas | Monto total |
|---|--------|-----------|----------|-------------|
"""

for idx, (_, r) in enumerate(top_100.head(30).iterrows(), 1):
    report += f"| {idx} | {str(r['cuenta'])[:70]} | {r['frecuencia']} | {r['empresas_distintas']} | ${r['total_montos']:,.0f} |\n"

report += f"""
[Las 100 cuentas completas están en top_accounts.xlsx]

## 3. Match contra diccionario

| Tipo de match | Cuentas | % del total | Interpretación |
|--------------|---------|------------|----------------|
"""

match_interpretations = {
    'EXACT_MATCH': 'Ya existen en el diccionario (debieran estar clasificadas)',
    'NORMALIZED_MATCH': 'Coinciden al normalizar mayúsculas/tildes',
    'FUZZY_MATCH': 'Coinciden con fuzzy matching (≥88% similitud)',
    'ABBREVIATION': 'Contienen abreviaturas expandibles',
    'NEW_ACCOUNT': 'Cuentas válidas no presentes en el diccionario',
    'OCR_NOISE': 'Ruido de OCR (montos embebidos, caracteres extraños)',
    'PARSER_ARTIFACT': 'Artefactos del parser (fechas, encabezados)',
}

for k, v in match_counts.items():
    interp = match_interpretations.get(k, '')
    # Avoid double %
    report += f"| {k} | {v} | {v/len(all_names)*100:.1f}% | {interp} |\n"

report += f"""
## 4. Análisis detallado por categoría

### 4.1 Normalización ({norm_accounts + fuzzy_accounts} cuentas, {(norm_accounts+fuzzy_accounts)/len(all_names)*100:.1f}%)

- **NORMALIZED_MATCH**: {norm_accounts} cuentas — solo requieren quitar tildes y mayúsculas
- **FUZZY_MATCH**: {fuzzy_accounts} cuentas — requieren fuzzy matching (>88%)
- **Total recuperable**: {norm_accounts + fuzzy_accounts} cuentas

Estas cuentas ya existen en el diccionario pero con diferencias menores (tildes, espacios, puntuación).

### 4.2 Sinónimos ({synonym_accts_unique} cuentas, {synonym_accts_unique/len(all_names)*100:.1f}%)

Se detectaron **{len(synonym_df)} grupos de sinónimos** con un total de **{synonym_accts_unique} cuentas** involucradas.

Principales grupos:
"""

for _, r in synonym_df.head(10).iterrows():
    report += f"- Grupo {r['grupo']} (frecuencia {r['frecuencia']}): \"{r['nombre_principal'][:60]}\" → {r['variantes'][:80]}\n"

report += f"""
### 4.3 Abreviaturas ({abbrev_accounts} cuentas, {abbrev_accounts/len(all_names)*100:.1f}%)

Se detectaron **{len(abbr_summary)} abreviaturas distintas** en **{abbrev_accounts} cuentas**.

| Abreviatura | Expansión sugerida | Frecuencia | Cuentas | Confianza |
|------------|-------------------|-----------|---------|-----------|
"""

for _, r in abbr_summary.head(15).iterrows():
    report += f"| {r['abreviatura']} | {r['expansion_sugerida']} | {r['frecuencia']} | {r['n_cuentas']} | {r['confianza']} |\n"

report += f"""
### 4.4 Nuevas entradas en diccionario ({new_dict_accounts} cuentas, {new_dict_accounts/len(all_names)*100:.1f}%)

**{new_dict_accounts} cuentas** válidas no existen en el diccionario.
Representan **{new_dict_accounts/len(valid_names)*100:.1f}%** de las cuentas válidas sin clasificar.

Estas cuentas requieren:
1. Revisión manual para determinar su código estándar
2. Inserción en el diccionario
3. Re-ejecución del pipeline

### 4.5 Patrones detectables ({pattern_accts_unique} cuentas, {pattern_accts_unique/len(all_names)*100:.1f}%)

| Patrón | Frecuencia | Cuentas |
|--------|-----------|---------|
"""

for _, r in pat_summary.head(15).iterrows():
    report += f"| {r['patron']} | {r['frecuencia']} | {r['n_cuentas']} |\n"

report += f"""
### 4.6 Problemas del parser ({parser_artifact_accounts} cuentas, {parser_artifact_accounts/len(all_names)*100:.1f}%)

**{parser_artifact_accounts} cuentas** identificadas como artefactos del parser:
- Fechas ("Al 31 de Diciembre de", "Enero a Diciembre")
- Encabezados de página ("Comuna : Bulnes PAGINA :")
- Nombres de empresa ("Rengo", "MONTEVIDEO")
- Títulos de sección

Estas cuentas NO deben clasificarse; deben filtrarse en el parser.

### 4.7 Problemas de OCR ({ocr_noise_accounts} cuentas, {ocr_noise_accounts/len(all_names)*100:.1f}%)

**{ocr_noise_accounts} cuentas** con probable ruido de OCR:
- Montos numéricos embebidos en el nombre de cuenta
- Caracteres extraños (|, _, /, corchetes)
- Texto irreconocible

Ejemplos:
"""

ocr_examples = [n for n in all_names if is_ocr_noise(n)][:10]
for n in ocr_examples:
    report += f"- \"{str(n)[:80]}\"\n"

parser_examples = [n for n in all_names if is_parser_artifact(n)][:10]
report += f"""
Ejemplos de artefactos del parser:
"""
for n in parser_examples:
    report += f"- \"{str(n)[:80]}\"\n"

report += f"""
## 5. Estimación de impacto

| Prioridad | Acción | Cuentas | % cobertura | Esfuerzo | Retorno esperado |
|-----------|--------|---------|------------|----------|-----------------|
| 1 (Alta) | Normalización (fuzzy + normalized) | {p1_norm} | {p1_norm/len(all_names)*100:.1f}% | Bajo | Alto — implementación simple, impacto inmediato |
| 1 (Alta) | Sinónimos | {p1_synonym} | {p1_synonym/len(all_names)*100:.1f}% | Bajo | Medio — mejora consistencia |
| 2 (Media) | Abreviaturas | {p2_abbrev} | {p2_abbrev/len(all_names)*100:.1f}% | Medio | Medio — expandir antes de matching |
| 2 (Media) | Reglas (patrones) | {p2_patterns} | {p2_patterns/len(all_names)*100:.1f}% | Medio | Medio — cubre familias completas |
| 3 (Baja) | Nuevas entradas diccionario | {p3_dict} | {p3_dict/len(all_names)*100:.1f}% | Alto | Alto pero requiere revisión manual |
| — | Filtrar artefactos parser | {parser_artifact_accounts} | {parser_artifact_accounts/len(all_names)*100:.1f}% | Bajo | Mejora métricas, no cobertura |
| — | Limpiar ruido OCR | {ocr_noise_accounts} | {ocr_noise_accounts/len(all_names)*100:.1f}% | Alto | Depende del origen |

## 6. Respuestas a preguntas clave

### ¿Por qué las cuentas no se clasifican?

| Causa raíz | % de cuentas afectadas |
|-----------|----------------------|
| No existen en el diccionario | {new_dict_accounts/len(all_names)*100:.1f}% |
| Ruido de OCR | {ocr_noise_accounts/len(all_names)*100:.1f}% |
| Abreviaturas no expandidas | {abbrev_accounts/len(all_names)*100:.1f}% |
| Diferencias menores (normalización) | {(norm_accounts+fuzzy_accounts)/len(all_names)*100:.1f}% |
| Artefactos del parser | {parser_artifact_accounts/len(all_names)*100:.1f}% |

### ¿Qué porcentaje puede resolverse con normalización?

**{(norm_accounts+fuzzy_accounts)/len(valid_names)*100:.1f}%** de las cuentas válidas ({norm_accounts+fuzzy_accounts} cuentas).

### ¿Qué porcentaje puede resolverse con sinónimos?

**{synonym_accts_unique/len(valid_names)*100:.1f}%** de las cuentas válidas ({synonym_accts_unique} cuentas).

### ¿Qué porcentaje requiere ampliar el diccionario?

**{new_dict_accounts/len(valid_names)*100:.1f}%** de las cuentas válidas ({new_dict_accounts} cuentas) — es la causa principal.

### ¿Qué porcentaje corresponde a problemas del parser?

**{parser_artifact_accounts/len(all_names)*100:.1f}%** del total ({parser_artifact_accounts} cuentas).

### ¿Qué porcentaje corresponde a OCR?

**{ocr_noise_accounts/len(all_names)*100:.1f}%** del total ({ocr_noise_accounts} cuentas).

## 7. Recomendaciones priorizadas

### Sprint 1 (Alta prioridad — máximo retorno con mínimo esfuerzo)

1. **Implementar normalización de texto en el pipeline de matching**:
   - Quitar tildes antes de comparar contra el diccionario
   - Ignorar mayúsculas/minúsculas
   - Eliminar puntuación y espacios múltiples
   - Impacto estimado: **+{norm_accounts} cuentas clasificadas**

2. **Agregar fuzzy matching con threshold ≥88%**:
   - Capturar variantes ortográficas menores
   - Impacto estimado: **+{fuzzy_accounts} cuentas clasificadas**

### Sprint 2 (Prioridad media)

3. **Expandir abreviaturas antes del matching**:
   - Crear tabla de expansión ({len(abbr_summary)} abreviaturas identificadas)
   - Impacto estimado: **+{abbrev_accounts} cuentas clasificadas**

4. **Crear reglas por patrón**:
   - {len(pat_summary)} patrones identificados (Gastos *, Banco *, etc.)
   - Impacto estimado: **+{pattern_accts_unique} cuentas clasificadas**

### Sprint 3 (Prioridad baja — esfuerzo alto)

5. **Ampliar el diccionario con {new_dict_accounts} nuevas entradas**:
   - Requiere revisión manual de cada cuenta
   - Es la acción de mayor impacto individual ({new_dict_accounts/len(valid_names)*100:.1f}% de cuentas válidas)

6. **Filtrar artefactos del parser**:
   - Ignorar fechas, encabezados, nombres de empresa
   - {parser_artifact_accounts} cuentas dejarían de aparecer como "no clasificadas"

### Acción con mayor retorno esperado

**Normalización + Fuzzy matching**: implementación simple (días), sin revisión manual, recupera **{norm_accounts+fuzzy_accounts} cuentas ({((norm_accounts+fuzzy_accounts)/len(all_names)*100):.1f}%)**.

## 8. Conclusión

La causa principal de cuentas no clasificadas es la **ausencia en el diccionario** ({new_dict_accounts/len(all_names)*100:.1f}%).
Sin embargo, la acción con **mayor retorno inmediato** es la **normalización de texto** (bajo esfuerzo, impacto del {(norm_accounts+fuzzy_accounts)/len(all_names)*100:.1f}%).

Combinando normalización + sinónimos + abreviaturas + reglas se podría recuperar hasta **~{p1_synonym + p2_abbrev + p2_patterns + norm_accounts + fuzzy_accounts} cuentas** ({(p1_synonym + p2_abbrev + p2_patterns + norm_accounts + fuzzy_accounts)/len(all_names)*100:.1f}% del total), sin modificar el diccionario.

Para superar el **{new_dict_accounts/len(valid_names)*100:.1f}%** restante de cuentas válidas, se requiere ampliar el diccionario con revisión manual.
"""

(OUTPUT_DIR / 'gap_report.md').write_text(report, encoding='utf-8')
print(f"\n8. gap_report.md generated")
print(f"\n{'='*60}")
print(f"ALL OUTPUTS IN: {OUTPUT_DIR}")
print(f"{'='*60}")
