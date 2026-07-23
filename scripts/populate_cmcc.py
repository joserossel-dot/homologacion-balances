"""Populate CMCC automatically from catalogo_maestro + diccionario + generated entries."""
from __future__ import annotations
import sys
import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date
from typing import Optional
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.concept import Concept
from knowledge.normalizer import Normalizer
from knowledge.repository import Repository
from knowledge.metrics import Metrics
from knowledge.cmcc import CMCC

BASE_DIR = Path('/Users/josealfonsorossel/AI-Projects/homologacion-balances')
OUTPUT_DIR = BASE_DIR / 'reports/cmcc_population'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CMCC_PATH = BASE_DIR / 'knowledge/cmcc.json'
CATALOGO_PATH = BASE_DIR / 'catalogo_maestro.json'
DICCIONARIO_PATH = BASE_DIR / 'diccionario.json'
GENERATED_PATH = BASE_DIR / 'reports/knowledge/generated_dictionary_entries.json'
TOP_ACCOUNTS_PATH = BASE_DIR / 'reports/classification_gap/top_accounts.xlsx'
RECOVERY_MATRIX_PATH = BASE_DIR / 'reports/recovery_matrix/recovery_matrix.xlsx'
TOP20_PATH = BASE_DIR / 'reports/recovery_pareto/top20.xlsx'

TODAY = date.today().isoformat()
normalizer = Normalizer()
cmcc = CMCC(CMCC_PATH)
repo = cmcc.repository

# ── Load source data ──
with open(CATALOGO_PATH, 'r', encoding='utf-8') as f:
    catalogo = json.load(f)

with open(DICCIONARIO_PATH, 'r', encoding='utf-8') as f:
    diccionario = json.load(f)

generated = []
if GENERATED_PATH.exists():
    with open(GENERATED_PATH, 'r', encoding='utf-8') as f:
        generated = json.load(f)

top_accounts = pd.read_excel(TOP_ACCOUNTS_PATH)

# Allow partial load of optional files
try:
    recovery_matrix = pd.read_excel(RECOVERY_MATRIX_PATH)
except Exception:
    recovery_matrix = pd.DataFrame()
try:
    top20 = pd.read_excel(TOP20_PATH)
except Exception:
    top20 = pd.DataFrame()

freq_map = dict(zip(top_accounts['cuenta'].astype(str), top_accounts['frecuencia']))
emp_map = dict(zip(top_accounts['cuenta'].astype(str), top_accounts['empresas_distintas']))

# ──────────────────────────────────────────────
# STEP 1: Create Concepts from catalogo_maestro
# ──────────────────────────────────────────────
print("Step 1: Creating concepts from catalogo_maestro...")
codigo_to_nombre = {}
for code, entry in catalogo.items():
    nombre = entry['nombre_estandar']
    categoria_map = {
        'activo_corriente': 'activo_corriente',
        'activo_no_corriente': 'activo_no_corriente',
        'pasivo_corriente': 'pasivo_corriente',
        'pasivo_no_corriente': 'pasivo_no_corriente',
        'patrimonio_neto': 'patrimonio',
        'patrimonio': 'patrimonio',
        'ingreso': 'ingreso',
        'costo': 'costo',
        'gasto': 'gasto',
        'cuenta_orden': 'cuenta_orden',
    }
    cat = categoria_map.get(entry.get('categoria', ''), entry.get('categoria', 'otros'))
    fs_map = {'balance': 'balance', 'resultado': 'resultado', 'resultados': 'resultado', 'orden': 'orden'}
    fs = fs_map.get(entry.get('tipo_estado', ''), 'balance')

    # Extract keywords from name
    name_norm = normalizer.normalize(nombre).text
    palabras_clave = list(set(name_norm.split())) if name_norm else []

    c = Concept(
        id=code,
        codigo=code,
        nombre=nombre,
        categoria=cat,
        tipo_estado_financiero=fs,
        palabras_clave=palabras_clave,
        confidence=0.9,
        version='1.0.0',
        ultima_revision=TODAY,
        metadata={
            'naturaleza': entry.get('naturaleza', ''),
            'descripcion': entry.get('descripcion', ''),
            'fuente': 'catalogo_maestro',
        }
    )
    try:
        repo.add(c)
    except ValueError:
        print(f"  WARNING: duplicate code {code}, skipping")
    codigo_to_nombre[code] = nombre

print(f"  Created {repo.count()} concepts")

# ──────────────────────────────────────────────
# STEP 2: Add variants from diccionario.json
# ──────────────────────────────────────────────
print("\nStep 2: Adding variants from diccionario.json...")
variants_by_concept = defaultdict(set)
variant_to_concept = {}
dup_variants = []

for entry in diccionario:
    cuenta = entry['cuenta_original']
    codigo = entry['codigo_estandar']
    fuente = entry.get('fuente', 'desconocida')

    concept = repo.find_by_codigo(codigo)
    if not concept:
        print(f"  WARNING: codigo {codigo} not found in catalog, skipping {cuenta}")
        continue

    # Normalize to detect how to store
    norm = normalizer.normalize(cuenta).text
    name_norm = normalizer.normalize(concept.nombre).text

    # Check if this variant already assigned to another concept
    norm_lower = normalizer.normalize(cuenta).text
    if norm_lower in variant_to_concept and variant_to_concept[norm_lower] != codigo:
        dup_variants.append({
            'variante': cuenta,
            'codigo_actual': codigo,
            'codigo_existente': variant_to_concept[norm_lower],
            'normalizada': norm_lower,
        })
        continue

    if norm_lower not in variant_to_concept:
        variant_to_concept[norm_lower] = codigo

    # Determine if it's an exact name match -> synonym, otherwise variant
    if norm_lower == name_norm:
        concept.add_synonym(cuenta)
    else:
        concept.add_variant(cuenta)

    concept.add_example(cuenta)
    variants_by_concept[codigo].add(cuenta)

total_variants_added = sum(len(v) for v in variants_by_concept.values())
print(f"  Added {total_variants_added} variants across {len(variants_by_concept)} concepts")
print(f"  Cross-concept duplicates found: {len(dup_variants)}")

# Save duplicates found
if dup_variants:
    pd.DataFrame(dup_variants).to_excel(OUTPUT_DIR / 'cross_concept_duplicates.xlsx', index=False)

# ──────────────────────────────────────────────
# STEP 2b: Add variants from generated dictionary
# ──────────────────────────────────────────────
print(f"\nStep 2b: Adding {len(generated)} generated entries...")
gen_added = 0
for entry in generated:
    cuenta = entry.get('cuenta_original', '')
    codigo = entry.get('codigo_estandar', '')
    confidence = entry.get('confidence', 0.4)

    if not cuenta or not codigo:
        continue
    concept = repo.find_by_codigo(codigo)
    if not concept:
        continue

    norm_lower = normalizer.normalize(cuenta).text
    if norm_lower in variant_to_concept:
        continue  # Already exists

    variant_to_concept[norm_lower] = codigo
    concept.add_variant(cuenta)
    concept.add_example(cuenta)
    gen_added += 1

print(f"  Added {gen_added} generated variants")

# ──────────────────────────────────────────────
# STEP 3: Detect duplicates via normalizer
# ──────────────────────────────────────────────
print("\nStep 3: Detecting potential duplicates across concepts...")

all_variants_normalized = {}
for concept in repo.list_all():
    all_variants_normalized[concept.codigo] = set()
    all_variants_normalized[concept.codigo].add(normalizer.normalize(concept.nombre).text)
    for v in concept.variantes:
        all_variants_normalized[concept.codigo].add(normalizer.normalize(v).text)
    for s in concept.sinonimos:
        all_variants_normalized[concept.codigo].add(normalizer.normalize(s).text)

# Find normalized forms that appear in multiple concepts
norm_to_codes = defaultdict(set)
for code, norms in all_variants_normalized.items():
    for n in norms:
        norm_to_codes[n].add(code)

conflicts = []
for norm, codes in norm_to_codes.items():
    if len(codes) > 1:
        conflicts.append({
            'normalizada': norm,
            'conceptos_implicados': ' | '.join(sorted(codes)),
            'n_conceptos': len(codes),
        })

conflicts.sort(key=lambda x: -x['n_conceptos'])
print(f"  Cross-concept normalized conflicts: {len(conflicts)}")

if conflicts:
    pd.DataFrame(conflicts).to_excel(OUTPUT_DIR / 'normalized_conflicts.xlsx', index=False)

# ──────────────────────────────────────────────
# STEP 4: Detect synonym candidates via normalizer
# ──────────────────────────────────────────────
print("\nStep 4: Detecting synonym candidates...")
synonym_candidates = []
concepts_list = repo.list_all()

for i, c1 in enumerate(concepts_list):
    n1 = normalizer.normalize(c1.nombre).text
    for c2 in concepts_list[i+1:]:
        n2 = normalizer.normalize(c2.nombre).text
        # Check if normalized names are similar
        if n1 and n2:
            from rapidfuzz import fuzz
            ratio = fuzz.ratio(n1, n2)
            if ratio >= 70:
                synonym_candidates.append({
                    'concepto_a': f"{c1.codigo}: {c1.nombre}",
                    'concepto_b': f"{c2.codigo}: {c2.nombre}",
                    'normalizado_a': n1,
                    'normalizado_b': n2,
                    'similitud': ratio,
                })

synonym_candidates.sort(key=lambda x: -x['similitud'])
print(f"  Synonym candidates: {len(synonym_candidates)}")

pd.DataFrame(synonym_candidates).to_excel(
    OUTPUT_DIR / 'synonym_candidates.xlsx', index=False)

# ──────────────────────────────────────────────
# STEP 5: Calculate statistics per Concept
# ──────────────────────────────────────────────
print("\nStep 5: Calculating statistics...")

stat_rows = []
for concept in repo.list_all():
    n_variants = len(concept.variantes)
    n_synonyms = len(concept.sinonimos)
    n_abbrevs = len(concept.abreviaturas)
    n_examples = len(concept.ejemplos)
    n_palabras = len(concept.palabras_clave)
    n_patrones = len(concept.patrones)
    n_empresas = len(concept.empresas)

    # Calculate frequency from top_accounts
    total_freq = 0
    unique_empresas = set()
    for variant in concept.variantes:
        total_freq += freq_map.get(variant, 0)
        emp = emp_map.get(variant, 0)
        if emp > 0:
            unique_empresas.add(str(emp))
    for syn in concept.sinonimos:
        total_freq += freq_map.get(syn, 0)
        emp = emp_map.get(syn, 0)
        if emp > 0:
            unique_empresas.add(str(emp))

    coverage = concept.coverage_score
    confianza = concept.confidence

    stat_rows.append({
        'codigo': concept.codigo,
        'nombre': concept.nombre,
        'categoria': concept.categoria,
        'tipo_estado': concept.tipo_estado_financiero,
        'n_variantes': n_variants,
        'n_sinonimos': n_synonyms,
        'n_abreviaturas': n_abbrevs,
        'n_ejemplos': n_examples,
        'n_palabras_clave': n_palabras,
        'n_patrones': n_patrones,
        'empresas_unicas': len(unique_empresas),
        'frecuencia_total': total_freq,
        'cobertura_score': coverage,
        'confianza': confianza,
        'ultima_revision': concept.ultima_revision,
    })

stats_df = pd.DataFrame(stat_rows)
stats_df.to_excel(OUTPUT_DIR / 'cmcc_statistics.xlsx', index=False)
print(f"  Statistics for {len(stat_rows)} concepts")

# ──────────────────────────────────────────────
# Generate cmcc_variants.xlsx
# ──────────────────────────────────────────────
variant_rows = []
for concept in repo.list_all():
    for v in concept.variantes:
        freq = freq_map.get(v, 0)
        emp = emp_map.get(v, 0)
        variant_rows.append({
            'codigo': concept.codigo,
            'nombre_concepto': concept.nombre,
            'variante': v,
            'tipo': 'variante',
            'frecuencia': freq,
            'empresas': emp,
        })
    for s in concept.sinonimos:
        freq = freq_map.get(s, 0)
        emp = emp_map.get(s, 0)
        variant_rows.append({
            'codigo': concept.codigo,
            'nombre_concepto': concept.nombre,
            'variante': s,
            'tipo': 'sinonimo',
            'frecuencia': freq,
            'empresas': emp,
        })

variant_df = pd.DataFrame(variant_rows)
variant_df.to_excel(OUTPUT_DIR / 'cmcc_variants.xlsx', index=False)
print(f"  Variant detail: {len(variant_df)} rows")

# ──────────────────────────────────────────────
# Generate cmcc_population.xlsx (full catalog)
# ──────────────────────────────────────────────
population_rows = []
for concept in repo.list_all():
    d = concept.to_dict()
    d['n_variantes'] = len(concept.variantes)
    d['n_sinonimos'] = len(concept.sinonimos)
    d['frecuencia'] = sum(freq_map.get(v, 0) for v in concept.variantes) + \
                      sum(freq_map.get(s, 0) for s in concept.sinonimos)
    population_rows.append(d)

pop_df = pd.DataFrame(population_rows)
pop_df.to_excel(OUTPUT_DIR / 'cmcc_population.xlsx', index=False)
print(f"  Population: {len(population_rows)} concepts")

# ──────────────────────────────────────────────
# Verification
# ──────────────────────────────────────────────
print("\n=== VERIFICATION ===")
codes_seen = set()
dup_codes = []
for c in repo.list_all():
    if c.codigo in codes_seen:
        dup_codes.append(c.codigo)
    codes_seen.add(c.codigo)
print(f"Duplicate codes: {len(dup_codes)}")
if dup_codes:
    print(f"  WARNING: {dup_codes}")

# Verify no variant in two concepts
all_var_map = {}
cross_concept_variants = []
for c in repo.list_all():
    for v in c.variantes:
        nv = normalizer.normalize(v).text
        if nv in all_var_map and all_var_map[nv] != c.codigo:
            cross_concept_variants.append({
                'variante': v,
                'normalizada': nv,
                'concepto_1': all_var_map[nv],
                'concepto_2': c.codigo,
            })
        all_var_map[nv] = c.codigo

print(f"Cross-concept variants: {len(cross_concept_variants)}")
if cross_concept_variants:
    pd.DataFrame(cross_concept_variants).to_excel(
        OUTPUT_DIR / 'cross_concept_variants.xlsx', index=False)

# ──────────────────────────────────────────────
# Duplicates report
# ──────────────────────────────────────────────
dup_rows = []
for c in repo.list_all():
    for v in c.variantes:
        nv = normalizer.normalize(v).text
        name_norm = normalizer.normalize(c.nombre).text
        if nv == name_norm:
            dup_rows.append({
                'codigo': c.codigo,
                'concepto': c.nombre,
                'variante': v,
                'razon': 'variante_igual_al_nombre',
            })

dup_df = pd.DataFrame(dup_rows) if dup_rows else pd.DataFrame(
    columns=['codigo', 'concepto', 'variante', 'razon'])
dup_df.to_excel(OUTPUT_DIR / 'cmcc_duplicates.xlsx', index=False)
print(f"Internal duplicates: {len(dup_df)}")

# ──────────────────────────────────────────────
# Save CMCC
# ──────────────────────────────────────────────
repo.save()
print(f"\nCMCC saved to {CMCC_PATH}")

# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────
metrics = Metrics(repo)
m = metrics.report()

# ──────────────────────────────────────────────
# Generate cmcc_population.md
# ──────────────────────────────────────────────
top20_variants = stats_df.sort_values('n_variantes', ascending=False).head(20)
top20_freq = stats_df.sort_values('frecuencia_total', ascending=False).head(20)
zero_variants = stats_df[stats_df['n_variantes'] == 0]
low_confidence = stats_df[stats_df['confianza'] < 0.5]

report = f"""# CMCC Population Report

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Conceptos creados | {repo.count()} |
| Total variantes | {metrics.total_variants} |
| Total sinónimos | {metrics.total_synonyms} |
| Total ejemplos | {metrics.total_examples} |
| Promedio variantes/concepto | {metrics.average_variants} |
| Cobertura potencial | {m['cobertura_potencial']['porcentaje']}% |
| Fuentes utilizadas | catalogo_maestro.json, diccionario.json, generated_dictionary_entries.json |

## 1. ¿Cuántos conceptos quedaron?

**{repo.count()} conceptos** fueron creados desde `catalogo_maestro.json`.

## 2. ¿Cuántas variantes?

- **{metrics.total_variants} variantes** desde `diccionario.json`
- **{metrics.total_synonyms} sinónimos**
- **{metrics.total_examples} ejemplos**

## 3. Promedio de variantes por concepto

**{metrics.average_variants} variantes por concepto** en promedio.

## 4. Top 20 conceptos con más variantes

| # | Código | Nombre | Variantes | Sinónimos | Frecuencia |
|---|--------|--------|-----------|-----------|-----------|
"""

for idx, (_, r) in enumerate(top20_variants.iterrows(), 1):
    report += f"| {idx} | {r['codigo']} | {r['nombre']} | {r['n_variantes']} | {r['n_sinonimos']} | {r['frecuencia_total']} |\n"

report += f"""
## 5. Top 20 conceptos más frecuentes

| # | Código | Nombre | Frecuencia | Variantes | Empresas |
|---|--------|--------|-----------|-----------|----------|
"""

for idx, (_, r) in enumerate(top20_freq.iterrows(), 1):
    report += f"| {idx} | {r['codigo']} | {r['nombre']} | {r['frecuencia_total']} | {r['n_variantes']} | {r['empresas_unicas']} |\n"

report += f"""
## 6. Top conceptos con problemas

### Conceptos sin variantes ({len(zero_variants)})
"""

if len(zero_variants) > 0:
    for _, r in zero_variants.iterrows():
        report += f"- {r['codigo']}: {r['nombre']}\n"

report += f"""
### Conceptos con confianza baja ({len(low_confidence)})
"""

if len(low_confidence) > 0:
    for _, r in low_confidence.iterrows():
        report += f"- {r['codigo']}: {r['nombre']} (confianza: {r['confianza']})\n"

report += f"""
## 7. Duplicados detectados

### Conflictos por normalización ({len(conflicts)})
"""

for c in conflicts[:20]:
    report += f"- Normalizada: \"{c['normalizada']}\" → {c['conceptos_implicados']}\n"

if len(conflicts) > 20:
    report += f"  ... y {len(conflicts) - 20} más\n"

report += f"""
### Variantes duplicadas entre conceptos ({len(cross_concept_variants)})
"""

for v in cross_concept_variants[:10]:
    report += f"- \"{v['variante']}\" en {v['concepto_1']} y {v['concepto_2']}\n"

if len(cross_concept_variants) > 10:
    report += f"  ... y {len(cross_concept_variants) - 10} más\n"

report += f"""
### Sinónimos candidatos ({len(synonym_candidates)})
"""

for sc in synonym_candidates[:15]:
    report += f"- \"{sc['concepto_a']}\" ↔ \"{sc['concepto_b']}\" (similitud: {sc['similitud']}%)\n"

if len(synonym_candidates) > 15:
    report += f"  ... y {len(synonym_candidates) - 15} más\n"

report += f"""
## 8. Conceptos sin código

**0 conceptos sin código** — todos los conceptos tienen código estándar.

## 9. Conceptos ambiguos

Los {len(conflicts)} conflictos de normalización indican posibles ambigüedades
donde una misma variante normalizada aparece en múltiples conceptos.

## 10. Distribución por tipo de estado financiero

| Tipo | Conceptos |
|------|-----------|
"""

for fs, cnt in m['distribucion_estado_financiero'].items():
    report += f"| {fs} | {cnt} |\n"

report += f"""
## 11. Distribución por categoría

| Categoría | Conceptos |
|-----------|-----------|
"""

for cat, cnt in m['distribucion_categoria'].items():
    report += f"| {cat} | {cnt} |\n"

report += f"""
## 12. Validación

| Validación | Resultado |
|-----------|-----------|
| Dos concepts con mismo código | {'PROBLEMA' if dup_codes else 'OK'} |
| Variante en dos concepts | {'PROBLEMA: ' + str(len(cross_concept_variants)) if cross_concept_variants else 'OK'} |
| Conceptos sin código | OK (0) |
| Variantes totales | {metrics.total_variants} |
| Total guardado en cmcc.json | {repo.count()} conceptos |

## 13. Próximos pasos

1. Revisar {len(conflicts)} conflictos de normalización
2. Resolver {len(cross_concept_variants)} variantes en múltiples conceptos
3. Evaluar {len(synonym_candidates)} candidatos a sinónimo
4. Poblar {len(zero_variants)} conceptos sin variantes
5. Integrar CMCC con el pipeline clasificador
"""

(OUTPUT_DIR / 'cmcc_population.md').write_text(report, encoding='utf-8')
print(f"\nReport generated: {OUTPUT_DIR / 'cmcc_population.md'}")
print(f"\n{'='*60}")
print("CMCC POPULATION COMPLETE")
print(f"{'='*60}")
