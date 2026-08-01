# Sprint 37 — Cierre Definitivo
## Accounting Knowledge Engine (Capa de Conocimiento Contable)

**Fecha de cierre:** 2026-08-01
**Rama:** `sprint-1-context-aware-hygiene`
**Objetivo:** Construir una capa de conocimiento adicional (sinónimos, normalización, reglas especiales, auditoría y cobertura) para mejorar la precisión del clasificador en Sprint 38.

---

## 1. Resumen ejecutivo

El sprint entrega una **capa de conocimiento contable chilena, puramente aditiva**, preparada para integrarse al clasificador en Sprint 38. Cumple todas las restricciones duras: **no se modificó** el Parser Universal, el HomologationPipeline, el RuleProcessor, los extractores ni la lógica de clasificación existente.

Se construyeron cuatro componentes nuevos de conocimiento (normalizador, sinónimos curados, reglas especiales, catálogo ampliado) y **tres herramientas de análisis** (auditoría del catálogo, descubrimiento de variantes en el corpus y reporte de cobertura). Todo se dejó como capa pura; la integración queda deliberadamente para el siguiente sprint.

Resultados clave:
- Catálogo maestro: **61 cuentas** (52 → 61, +9 nuevas).
- Sinónimos curados: **61/61 cuentas** con conocimiento (332 sinónimos + 318 variantes).
- Reglas especiales chilenas: **19 reglas** (6 de ellas sin código específico → candidatas a nuevas cuentas).
- Cobertura real (`gold_standard.db`): **80.3%** de los nombres de cuenta conocidos son reconocibles.
- Descubrimiento en corpus (725 docs): **1004 variantes** reales detectadas, **821 candidatas nuevas**.
- Suite de tests: **2446 passed en verde**.

---

## 2. Archivos creados

| Archivo | Tipo | Fase |
|---------|------|------|
| `account_name_normalizer.py` | Módulo de conocimiento (normalizador configurable) | FASE 4 |
| `special_account_rules.py` | Módulo de conocimiento (19 reglas contables chilenas) | FASE 5 |
| `tools/build_account_synonyms.py` | Builder de sinónimos curados | FASE 2 |
| `tools/audit_account_catalog.py` | Auditoría del catálogo maestro | FASE 1 |
| `tools/build_synonym_candidates.py` | Descubrimiento de variantes en el corpus | FASE 3 |
| `tools/account_coverage.py` | Reporte de cobertura de la capa | FASE 8 |
| `tests/test_account_knowledge.py` | Tests unitarios de la capa (36 tests) | FASE 9 |

## 3. Archivos modificados

| Archivo | Cambio | Fase |
|---------|--------|------|
| `catalogo_maestro.json` | +9 cuentas (PAT.06–11, ER.17–19); 6 cuentas marcadas `clasificable: false` | FASE 6/7 |
| `tests/test_catalog_selection.py` | `CUENTAS_CALCULO` actualizado (+ER.19) | FASE 6/7 |

*No se tocó ningún flujo de parsing/clasificación existente.*

## 4. Artefactos generados

| Artefacto | Contenido |
|-----------|-----------|
| `knowledge_base/account_synonyms.json` | Base de sinónimos por cuenta (61 cuentas, 623 claves) |
| `reports/catalog_audit.md` + `.json` | Auditoría del catálogo (duplicados, equivalentes, genéricos, sin uso) |
| `reports/synonym_candidates.md` + `.json` | Variantes reales del corpus por cuenta (1004 variantes, 821 nuevas) |
| `reports/account_coverage.md` + `.json` | Cobertura de gold_standard y corpus por capa |
| `reports/account_name_variants.json` | Caché de claves candidatas por documento (725 docs) |

## 5. Estadísticas finales

### Catálogo maestro
- Cuentas totales: **61** (antes 52).
- Nuevas: PAT.06 Capital Suscrito, PAT.07 Capital por Enterar (deudora), PAT.08 Reserva Técnica Revalorización AF, PAT.09 Utilidades Ejercicios Anteriores, PAT.10 Cuenta Particular Socios (deudora), PAT.11 Interés Minoritario, ER.17 Otros Ingresos, ER.18 Otros Egresos, ER.19 Resultado Antes de Impuestos.
- Cuentas de cálculo (`clasificable: false`): PAT.04, ER.03, ER.06, ER.08, ER.11, ER.19.

### Capa de sinónimos
- Cuentas curadas: **61/61**.
- Sinónimos: 332 · Variantes: 318 · Abreviaciones/OCR/digitación por cuenta.
- Claves de referencia (catálogo + sinónimos): **623**.

### Normalizador (`AccountNameNormalizer`)
- Abreviaciones: 84 · Símbolos: 34 · Plurales: 42 · Errores OCR: 11 · Stopwords: 19.
- Verificado: "Cta. Cte. Socios" → "cuenta corriente socios", "PRÉSTAMOS a Socios" → "prestamos a socios", "C.T.C. Accionistas" → "cuenta corriente accionistas".

### Reglas especiales
- Reglas totales: **19**.
- Con código de catálogo: 13.
- Sin código (candidatas a nuevas cuentas): 6 → Activos/Pasivos por Impuesto Diferido, Derivados, Dividendos por Pagar, Dividendos Anticipados, Leaseback.

### Auditoría del catálogo
- Duplicados de nombre: 2 (Relacionadas CP, Relacionadas LP — intencionales: activo vs pasivo).
- Pares equivalentes (sinónimos solapados): 8.
- Cuentas demasiado genéricas: 18.
- Cuentas sin uso conocido (ni gold ni reglas): 18.
- Campos faltantes / categorías inválidas: **0**.

### Descubrimiento en corpus
- Documentos procesados: **725** (620 PDF vía pdfplumber, 105 XLSX vía openpyxl).
- Variantes detectadas: **1004** en **56 cuentas**.
- Variantes candidatas nuevas (no curadas): **821**.
- Variantes sin match con el catálogo (Top 40 reportado): p. ej. "honorarios por pagar", "imposiciones por pagar", "activos intangibles distintos de plusvalía".

### Cobertura de la capa
- `gold_standard.db`: **188/234 nombres cubiertos (80.3%)** — 57 solo catálogo, 131 con sinónimos, 0 solo reglas.
- Variantes del corpus (frecuencia ≥ 3): **1270/3746 cubiertos (33.9%)**.

## 6. Estado de los tests — ✅ VERDE

Confirmado el día de cierre con la suite completa (65 archivos de test, sin incluir el scan de corpus en los tests por ser lento):

```
2446 passed, 5 warnings in 1628.21s (0:27:08)
```

- Suite completa: **2446 passed**.
- Nuevos tests de la capa (`test_account_knowledge.py`): **36 passed**.
- Tests de selección de catálogo (`test_catalog_selection.py`): **19 passed**.
- Verificación rápida conjunta de la capa: 55 passed en 0.16s.

## 7. Riesgos pendientes

1. **Corpus con ruido**: ~34% de cobertura sobre variantes del corpus refleja que una parte importante son artefactos de layout/OCR (líneas con dígitos, footnotes, nombres de empresa). El filtro de ruido elimina lo más evidente, pero el resto debe validarse humano.
2. **Solapamiento de sinónimos entre cuentas** (8 pares equivalentes): p. ej. AC.06S ↔ PAT.10, PAT.03 ↔ PAT.09, PAT.05 ↔ PAT.11. Riesgo de clasificación ambigua si no se define prioridad/desambiguación en Sprint 38.
3. **Cuentas sin uso conocido (18)**: no aparecen en gold_standard ni en reglas; pueden ser correctas pero sin evidencia de uso real aún.
4. **Cuentas de cálculo dentro de sinónimos**: las 6 cuentas `clasificable: false` siguen en el catálogo y en sinónimos; el clasificador deberá excluirlas como destino.
5. **Documentos sin texto nativo**: parte del corpus no tiene líneas extraíbles (corruptos/encrypted); la cobertura real podría ser mayor con OCR.

## 8. Deuda técnica

- **Match por Jaccard simple** en el descubridor de variantes: no usa distancia de edición ni lematización; variantes con singular/plural o errores OCR moderados pueden no agruparse. Se recomienda un scorer de similitud más fino (p. ej. difflib + tokens ponderados).
- **Umbral de confianza por capa no calibrado**: la cobertura mide "reconocimiento", no "clasificación correcta"; falta una métrica de precisión/recall con ground truth de clasificación.
- **Reporte de sinónimos candidatos no tiene mecanismo de revisión**: los 821 candidatos nuevos están en el JSON pero no hay workflow para marcarlos "aceptado/rechazado".
- **Caché de variantes (1.9 MB) sin versionado**: se regenera con `--no-cache` (~10 min); conviene versionarlo o regenerarlo solo bajo demanda.
- **Normalizador con lista fija**: plurales/abreviaciones manuales; una regla morfológica genérica (plural en -s/-es, acentos) reduciría la lista y mejoraría robustez.
- **Sin tests de integración con el clasificador**: deliberado (Sprint 38), pero el salto de "80% de cobertura" a "80% de precisión" requiere diseño.

## 9. Próximo sprint recomendado (Sprint 38)

**Integración del knowledge engine al clasificador** (respetando que Parser/RuleProcessor ya no se tocan):

1. **Motor de clasificación con scoring por capas**: catálogo → sinónimos → reglas especiales, con umbral de confianza y desambiguación de los 8 pares equivalentes.
2. **Pipeline de desambiguación**: prioridad de reglas especiales sobre sinónimos genéricos (p. ej. "Préstamos a Socios" → PAT.10 y no AC.03).
3. **Backfill de los 821 sinónimos candidatos**: revisión humana asistida (marcar aceptado/rechazado) y ampliación del `account_synonyms.json`.
4. **Nuevas cuentas candidatas**: evaluar 6 conceptos sin código (Impuestos Diferidos, Derivados, Dividendos, Leaseback) para agregarlos al catálogo.
5. **Métrica de precisión real**: ejecutar el clasificador sobre `gold_standard.db` con la nueva capa y medir exactitud vs. baseline actual.
6. **Exclusión de cuentas de cálculo** como destino de clasificación.
7. **Optimización del normalizador** (reglas morfológicas) para reducir la lista manual.
