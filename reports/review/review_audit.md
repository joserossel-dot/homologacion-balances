# Auditoría del Review Package

**Generado:** 2026-07-07
**Versión:** FASE 14A

---

## 1. Origen de cada fila

### Hoja 1 — Pendientes

```
review/review_metrics.py :: build_pending_rows()
  └─ Entrada: shadow_data.json (accounts[])
      ├─ Filtro: method IN ("unclassified", "unknown", "") OR confidence < 0.85
      ├─ Salida: 9,031 filas (de 10,672 totales)
      ├─ 8,762 → method = "unclassified" (incluye 100% de las no clasificadas)
      └─   269 → method tiene valor pero confidence < 0.85
```

**Columnas:** 41 definidas en `review_models.PENDING_COLUMNS`.  
**Columnas con datos reales:** 29.  
**Columnas editables vacías:** 12 (rellenadas con `""`).

### Hoja 2 — Baja Confianza

```
review/review_metrics.py :: build_low_confidence_rows()
  └─ Entrada: shadow_data.json (accounts[])
      ├─ Filtro: confidence < 0.85
      └─ Salida: 9,031 filas (coincide con Pendientes porque 8,762 tienen confidence=0.0)
```

### Hoja 3 — Conflictos

```
review/review_package_builder.py :: _build_conflicts()
  ├─ Entrada: gold_standard.db (gold_records)
  └─ Salida: 0 filas
      └─ Razón: ningún nombre de cuenta aparece con ≥2 códigos distintos en Gold Standard
```

### Hoja 4 — Reglas Propuestas

```
review/review_package_builder.py :: _build_proposed_rules()
  ├─ Entrada: knowledge_priority.xlsx
  ├─ Filtro: type = "new_semantic_rule"
  └─ Salida: 534 filas
```

### Hoja 5 — Sinónimos

```
review/review_package_builder.py :: _build_synonym_entries()
  ├─ Entrada: knowledge_synonyms.xlsx
  └─ Salida: 1,951 filas (variantes expandidas desde 393 grupos)
```

### Hoja 6 — Gold Standard

```
review/review_package_builder.py :: _build_gold_proposals()
  ├─ Entrada: generated_gold_standard.json
  └─ Salida: 185 filas
```

### Hoja 7 — Dashboard

```
review/review_metrics.py :: build_dashboard()
  └─ Entrada: shadow_data.json (accounts[])
```

### Hoja 8 — Log

```
review/review_package_builder.py :: _write_header_only()
  └→ Template vacío (1 fila de encabezados)
```

---

## 2. Criterios de inclusión

El Review Package **incluye toda cuenta que sea "unknown" o de baja confianza**:

| Categoría | Cantidad | % del total |
|---|---|---|
| **Total cuentas** | 10,672 | 100.0% |
| **Unclassified** (method="unclassified") | 8,762 | 82.1% |
| **Classified** | 1,910 | 17.9% |
| ├─ learning_exact | 1,049 | 9.8% |
| ├─ dictionary_fuzzy | 293 | 2.7% |
| ├─ dictionary_exact | 246 | 2.3% |
| ├─ code | 167 | 1.6% |
| └─ learning_fuzzy | 155 | 1.5% |
| **Semantic interpretadas** | 163 | 1.5% |
| **Semantic NO interpretadas** | 10,509 | 98.5% |
| **Pending** (Hoja 1) | **9,031** | **84.6%** |
| **Baja confianza** (Hoja 2) | **9,031** | **84.6%** |

**Conclusión:** El Review Package muestra 9,031 de 10,672 cuentas (84.6% del total).  
Solo excluye 1,641 cuentas que tienen confidence ≥ 0.85.

Las 1,641 excluidas son:
- 1,204 learning exact (conf ≥ 0.98)
- 155 learning fuzzy (conf ≥ 0.90)
- N/A dictionary exact (conf ≥ 0.95)
- 293 dictionary fuzzy (conf ≥ 0.90)
- 167 code (conf ≥ 0.95)

**Problema:** Las hojas 1 y 2 son casi idénticas (misma data, distinto ancho de columna).

---

## 3. Investigación "Caja"

### ¿Por qué aparece?

CAJA aparece **18 veces** en los datos, siempre con `method="unclassified"` y `confidence=0.0`.
Es 100% no clasificada. Todas aparecen en el Review Package.

### Detalle por grupo

| Grupo | Cantidad |
|---|---|
| validacion | 10 |
| edge_cases | 8 |

### Variantes de "Caja" en los datos

- "CAJA" (nombre exacto) — 18 ocurrencias
- "CAJA 5.519,080 PROVEEDORES" — nombre compuesto con monto
- "CAJA CHICA 100.000 CUENTAS POR PAGAR EMPRESA RELACION"
- "CAJA 189.933 PROVEEDORES"
- "CAJA 15.780.104 CTA ESPECIAL - LINEA DE CREDITO"
- "CAJA 360.000 PROVEEDORES"
- "CAJA GENERAL"
- "CAJA M/N"
- "CAJA CENTRAL"
- etc.

### Pipeline resultante

| Campo | Valor |
|---|---|
| Método | unclassified |
| Confidence | 0.0 |
| Final Code | None |
| Semantic Type | unknown |
| Learning | No match |

### ¿Debió aparecer?

**Sí.** Caja es una cuenta real (AC.01 - Caja y Bancos) que el pipeline no clasificó. Está correctamente incluida para revisión humana.

### Observación

Sin embargo, la mayoría de las variantes de "Caja" contienen montos embebidos en el nombre ("CAJA 5.519,080 PROVEEDORES"). El `classification_amount` no se condice con el monto en el nombre, porque el monto del nombre es el saldo y el `classification_amount` es un valor separado extraído del parser. Esto genera confusión: el revisor ve tanto el monto en el nombre como el monto en columna, sin saber cuál corresponde al saldo real.

---

## 4. Nombres mal extraídos

### Resumen

De 10,672 cuentas, **2,490 (23.3%)** tienen al menos un problema de extracción de nombre.

| Problema | Cuentas afectadas | % del total |
|---|---|---|
| **Prefijo numérico** (ej: "11051-0000 BANCO CHILE") | 2,259 | 21.2% |
| **Código ERP** (ej: "11051-0000") | 412 | 3.9% |
| **Contiene dos puntos** (ej: "66 Menos: Saldo...") | 293 | 2.7% |
| **Guiones bajos** | 34 | 0.3% |
| **Caracteres extraños** (paréntesis, llaves, etc.) | 725 | 6.8% |

### Top 100 nombres más problemáticos

(Incluido en `review_name_quality.xlsx`)

Casos extremos detectados:
- `717857|699 [fevos ques dañe agora RU gin TRA` — texto corrupto
- `1231890459/8814 Jonaés dota Desea` — texto corrupto
- `15250047] ——` — solo código
- `A _ — — á+>=>=+=—=2211 aa ed DOOM ANP FOdio` — basura OCR
- `724,199,977|_` — solo número

### ¿Dónde deberían limpiarse?

Estos nombres vienen del parser de balances (etapa de extracción desde PDF/Excel).  
El problema ocurre **antes** de llegar al Review Package. La limpieza debería ocurrir en:

1. **Parser de PDF** (etapa de extracción de texto) — aplicar regex para separar código de cuenta de nombre
2. **Pipeline de homologación** — en la normalización de nombres
3. **Opcional:** el Review Package podría mostrar el nombre "limpio" + el nombre "original" en columnas separadas

Actualmente no hay limpieza en ninguna etapa.

---

## 5. Columna del monto

### Diagnóstico

El Review Package **NO conserva** los montos desglosados por columna de origen (Activo, Pasivo, Patrimonio, Pérdida, Ganancia).

### ¿Qué se perdió?

En `shadow_data.json`, cada cuenta solo tiene:
```json
"classification_amount": 338.0   ← escalar único
```

No existen los campos:
- `amounts.assets`
- `amounts.liabilities`
- `amounts.losses`
- `amounts.profits`

### ¿Dónde se perdió?

En el pipeline de shadow. En `run_semantic_shadow.py`, cuando se serializan los resultados, solo se extrae `classification_amount` de cada cuenta, perdiendo el objeto `MonetaryAmounts` completo que sí tiene activo/pasivo/etc.

```python
# En run_semantic_shadow.py — extracción de shadow_data
account_data = {
    ...
    "classification_amount": account.classification_amount,  ← escalar
    ...
}
# Nunca se serializa account.amounts.assets, account.amounts.liabilities, etc.
```

### Impacto

En el Review Package, las columnas Activo/Pasivo/Patrimonio/Pérdida/Ganancia aparecen en el encabezado pero **siempre están vacías (0.0)**. El único monto disponible es "Monto Original" (columna O) que contiene `classification_amount`.

---

## 6. Contexto

### Disponible vs Exportado

| Campo | ¿Existe en shadow_data? | ¿Se exporta al Excel? |
|---|---|---|
| source_group | Sí: "validacion" / "edge_cases" | Sí → columna "Empresa" (B) |
| source_file | Sí: pero **vacío** para todas (10672/10672) | Sí → columna "Archivo" (F) |
| source_page | Sí: pero **0** para todas (10672/10672) | Sí → columna "Página" (G) |
| source_path | Sí: ruta del archivo | **NO se exporta** |
| account_code | Sí: pero **vacío** para 8,762 unclassified | Sí → columna "Código Original" (H) |
| standar_code | Sí: para 1,910 clasificadas | Sí → columna "Código sugerido" (X) |
| reason | Sí: texto de motivo | Sí → columna "Observaciones" (AC) |

### Problemas detectados

1. **source_file está vacío para TODAS las cuentas** — no se puede rastrear a qué archivo pertenece cada cuenta
2. **source_group solo tiene 2 valores** — "validacion" y "edge_cases" no son empresas reales
3. **source_page = 0 siempre** — no hay referencia a la página del balance
4. **No se exporta el contexto de fila** (cuentas anterior/posterior) — no existe en shadow_data

### Lo que falta

- RUT empresa
- Giro
- Año del balance
- Posición relativa (número de fila, cuentas vecinas)
- Nombre de empresa real (no "validacion"/"edge_cases")

---

## 7. Duplicados

### Estadísticas

| Métrica | Valor |
|---|---|
| Nombres únicos | 6,763 |
| Nombres con ≥2 apariciones | 1,831 (27.1% de los nombres) |
| Nombres con ≥10 apariciones | 84 (1.2%) |

### Top 10 nombres más repetidos

| Nombre | Veces | Grupos |
|---|---|---|
| UTILIDAD DEL EJERCICIO | 25 | 2 |
| Al 31 de Diciembre de | 24 | 2 |
| Capital Emitido | 22 | 1 |
| Ingresos de actividades ordinarias | 20 | 1 |
| CAJA | 18 | 2 |
| CAPITAL | 18 | 2 |
| REMUNERACIONES | 15 | 1 |
| PROVEEDORES | 15 | 2 |
| HONORARIOS POR PAGAR | 14 | 1 |
| Electricidad | 13 | 2 |

### ¿Son realmente duplicados?

**Sí y no.** Las 18 apariciones de "CAJA" son:
- Todas con `method="unclassified"`, `confidence=0.0`, `source_file=""`
- Se distribuyen en 2 grupos: validacion (10) y edge_cases (8)
- No se pueden distinguir porque no hay source_file, source_page, ni monto diferenciador

**Problema:** Sin más contexto (archivo, página, monto desglosado), no se puede determinar si son la misma cuenta en distintos archivos o copias idénticas de un mismo archivo mal particionado.

**Lista completa:** `review_top_duplicates.xlsx`

---

## 8. Priorización

### Fórmula actual

```python
def score(account):
    s = 0.0

    # Penalidad por no clasificar (0-50 puntos)
    if method IN ("unclassified", "unknown", ""):
        s += 50.0

    # Penalidad por confianza baja (0-30 puntos)
    if confidence < 0.5:       s += 30.0
    elif confidence < 0.85:    s += 15.0

    # Bonos por frecuencia y cobertura (0-45 puntos)
    s += min(frecuencia * 2.0, 20.0)       # hasta 20 pts
    s += min(cantidad_empresas * 5.0, 25.0) # hasta 25 pts

    # Bonos por detección alternativa (0-15 puntos)
    if semantic_hit:  s += 10.0
    if learning_hit:  s += 5.0

    return round(s, 1)
```

### Rango de scores observados

| Componente | Min | Max |
|---|---|---|
| Unknown penalty | 0 | 50 |
| Confidence penalty | 0 | 30 |
| Frequency bonus | 0 | 20 |
| Empresa bonus | 0 | 25 |
| Semantic boost | 0 | 10 |
| Learning boost | 0 | 5 |
| **Total** | **0** | **140** |

### Efectividad

**Problema fundamental:** El 82% de las cuentas son "unclassified" con confidence=0.0, frecuencia=1, cantidad_empresas=1. Esto produce:

```
score = 50 (unknown) + 30 (conf<0.5) + 2 (freq=1) + 5 (emp=1) = 87
```

El score de 87 es igual para la mayoría de las cuentas. No hay diferenciación real.

**Solo se diferencian cuando frecuencia > 10 o cantidad_empresas > 5**, lo que ocurre para aproximadamente 84 nombres (1.2%).

**El monto NO se considera en la priorización**, a pesar de ser el factor de impacto más relevante para un revisor humano.

---

## 9. Evaluación general

### Calificación: 5 / 10

### Fortalezas

1. **Estructura completa**: 8 hojas bien definidas, columnas con listas desplegables
2. **Formato profesional**: tabla con estilos, auto-filtro, congelar paneles
3. **Formato condicional**: rojo/naranja/amarillo/azul/verde según estado
4. **Cobertura total**: incluye 100% de cuentas no clasificadas + baja confianza
5. **Sin conflictos**: Gold Standard no tiene duplicados de código

### Debilidades

6. **Pérdida de montos desglosados**: Activo/Pasivo/Patrimonio/Pérdida/Ganancia siempre son 0.0 porque `shadow_data.json` solo exportó `classification_amount` escalar
7. **Contexto insuficiente**: `source_file` está vacío para todas las cuentas, `source_group` solo tiene 2 valores, `source_page` es 0
8. **Hojas 1 y 2 casi idénticas**: Pendientes (9,031) y Baja Confianza (9,031) tienen la misma data porque la mayoría son unclassified con confidence=0.0
9. **Priorización no considera monto**: el score ignora el valor monetario, que es el principal criterio de impacto para revisión
10. **Nombres sucios**: 23.3% de cuentas tienen prefijos numéricos, códigos ERP, caracteres extraños — sin limpieza previa
11. **Empresa no es empresa real**: "validacion" y "edge_cases" son categorías de prueba, no nombres de empresa
12. **Sin RUT, giro, año**: columnas declaradas pero siempre vacías
13. **Sin cuentas vecinas**: no hay contexto de fila (anterior/posterior)
14. **Alcance limitado**: solo 2 empresas/grupos representados (validacion, edge_cases)

### ¿Listo para revisión humana?

**Parcialmente.** La estructura del Excel es adecuada pero la calidad de los datos subyacentes limita severamente su utilidad. Un revisor humano vería 9,031 filas de cuentas sin clasificar, sin empresa real, sin monto desglosado, sin archivo de origen, con nombres sucios y priorización plana.

**Recomendación:** Mejorar `shadow_data.json` para incluir montos desglosados, contexto real de archivo/empresa, y nombres limpios antes de usar el Review Package con un revisor humano.

---

## 10. Archivos generados

| Archivo | Contenido |
|---|---|
| `review_audit.md` | Este informe |
| `review_statistics.xlsx` | Estadísticas por categoría |
| `review_top_duplicates.xlsx` | Top 100 nombres duplicados con montos |
| `review_name_quality.xlsx` | Top 200 nombres con problemas de extracción |
| `review_unknown_breakdown.xlsx` | Desglose por método de clasificación |
