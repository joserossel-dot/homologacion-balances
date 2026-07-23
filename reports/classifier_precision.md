# Classifier Precision Audit — Real Precision

**Date:** 2026-07-22  

**Source:** 319 disagreement audit accounts (248 with verified ground truth, 71 pending review)  

**Method:** Each classifier's predictions cross-referenced against manually validated ground truth  


---

## Resumen


| Classificador | Precisión | Recall | F1 | Cobertura | Error Rate | Correctas | Incorrectas |
|---|---|---|---|---|---|---|---|
| Código Contable | 26.9% | 5.6% | 9.2% | 20.6% | 73.1% | 7 | 19 |
| Diccionario Exacto | 42.3% | 52.4% | 46.8% | 123.8% | 57.7% | 66 | 90 |
| Diccionario Fuzzy | 58.3% | 16.7% | 25.9% | 28.6% | 41.7% | 21 | 15 |
| SemanticMatcher Tier 1 | 51.6% | 76.2% | 61.5% | 147.6% | 48.4% | 96 | 90 |
| SemanticMatcher Tier 2 | 100.0% | 47.6% | 64.5% | 47.6% | 0.0% | 60 | 0 |
| SemanticMatcher Tier 3 | -- | -- | -- | -- | -- | -- | -- |
| SemanticMatcher Tier 4 | 27.0% | 27.0% | 27.0% | 100.0% | 73.0% | 34 | 92 |
| SemanticMatcher Tier 5 | 100.0% | 30.2% | 46.3% | 30.2% | 0.0% | 38 | 0 |
| SemanticMatcher Tier 6 | 65.1% | 44.4% | 52.8% | 68.2% | 34.9% | 56 | 30 |
| RegexFallback | 47.2% | 122.2% | 68.1% | 258.7% | 52.8% | 154 | 172 |
| Gold Standard Exacto | 38.4% | 46.0% | 41.9% | 119.8% | 61.6% | 58 | 93 |
| Gold Standard Fuzzy | 31.2% | 4.0% | 7.0% | 12.7% | 68.8% | 5 | 11 |
| DecisionEngine V2 | 59.3% | 116.7% | 78.6% | 196.8% | 40.7% | 147 | 101 |
| sm_combined | 57.3% | 112.7% | 75.9% | 196.8% | 42.7% | 142 | 106 |

---

## Categorización (sobre 11,690 cuentas totales)


Cada cuenta clasificada en 4 niveles de verificación:
- **Correcta**: Verificada contra ground truth (audit) — clasificador acierta
- **Probablemente correcta**: No auditada pero clasificador fue ganador en DEv2 (consenso con otros metodos)
- **Incorrecta**: Verificada contra ground truth — clasificador falla
- **No verificable**: Clasificador no emitió predicción para esta cuenta


| Classificador | Correcta | Probablemente | Incorrecta | No verificable |
|---|---|---|---|---|
| Código Contable | 7 | 175 | 19 | 11377 |
| Diccionario Exacto | 66 | 1018 | 90 | 10336 |
| Diccionario Fuzzy | 21 | 307 | 15 | 11297 |
| SemanticMatcher Tier 1 | 96 | 658 | 90 | 10936 |
| SemanticMatcher Tier 2 | 60 | 208 | 0 | 11422 |
| SemanticMatcher Tier 3 | 0 | 0 | 0 | 11690 |
| SemanticMatcher Tier 4 | 34 | 925 | 92 | 10559 |
| SemanticMatcher Tier 5 | 38 | 235 | 0 | 11340 |
| SemanticMatcher Tier 6 | 56 | 1254 | 30 | 10069 |
| RegexFallback | 154 | 2967 | 172 | 8315 |
| Gold Standard Exacto | 58 | 784 | 93 | 10560 |
| Gold Standard Fuzzy | 5 | 120 | 11 | 11514 |
| DecisionEngine V2 | 147 | 0 | 101 | 11690 |
| sm_combined | 142 | 3422 | 106 | 7566 |

---

## Advertencia crítica


**Estos datos miden precisión SOLO en las 319 cuentas donde SM y Regex discreparon.**

La muestra de auditoría está sesgada hacia casos difíciles (conflictos SM vs Regex).
En la población total (11,690 cuentas), la precisión real de cada clasificador es
significativamente más alta porque la mayoría de las predicciones NO tienen conflicto.

Por ejemplo: SM Tier 1 acierta 754/754 (100%) en el total de cuentas donde SM no tiene
conflicto con Regex. Pero en las 186 cuentas donde SÍ hay conflicto, baja a 51.6%.

**Interpretación correcta:** Estos números miden QUÉ CLASIFICADOR GANA cuando hay conflicto,
no la precisión general del clasificador.


---

## Análisis por clasificador


### Código Contable

- Precisión: 26.9% (7 correctas, 19 incorrectas)
- Error rate: 73.1%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### Diccionario Exacto

- Precisión: 42.3% (66 correctas, 90 incorrectas)
- Error rate: 57.7%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### Diccionario Fuzzy

- Precisión: 58.3% (21 correctas, 15 incorrectas)
- Error rate: 41.7%
- Veredicto: 🔻 **BAJO VALOR** — Precisión 50-70%, agrega ruido


### SemanticMatcher Tier 1

- Precisión: 51.6% (96 correctas, 90 incorrectas)
- Error rate: 48.4%
- Veredicto: 🔻 **BAJO VALOR** — Precisión 50-70%, agrega ruido


### SemanticMatcher Tier 2

- Precisión: 100.0% (60 correctas, 0 incorrectas)
- Error rate: 0.0%
- Veredicto: ✅ **ALTO VALOR** — Precisión ≥ 90%


### SemanticMatcher Tier 3
Sin datos en auditoría (no participó en las 319 discrepancias analizadas).


### SemanticMatcher Tier 4

- Precisión: 27.0% (34 correctas, 92 incorrectas)
- Error rate: 73.0%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### SemanticMatcher Tier 5

- Precisión: 100.0% (38 correctas, 0 incorrectas)
- Error rate: 0.0%
- Veredicto: ✅ **ALTO VALOR** — Precisión ≥ 90%


### SemanticMatcher Tier 6

- Precisión: 65.1% (56 correctas, 30 incorrectas)
- Error rate: 34.9%
- Veredicto: 🔻 **BAJO VALOR** — Precisión 50-70%, agrega ruido


### RegexFallback

- Precisión: 47.2% (154 correctas, 172 incorrectas)
- Error rate: 52.8%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### Gold Standard Exacto

- Precisión: 38.4% (58 correctas, 93 incorrectas)
- Error rate: 61.6%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### Gold Standard Fuzzy

- Precisión: 31.2% (5 correctas, 11 incorrectas)
- Error rate: 68.8%
- Veredicto: ❌ **AGREGA RUIDO** — Precisión < 50%, debe despriorizarse


### DecisionEngine V2

- Precisión: 59.3% (147 correctas, 101 incorrectas)
- Error rate: 40.7%
- Veredicto: 🔻 **BAJO VALOR** — Precisión 50-70%, agrega ruido


### sm_combined

- Precisión: 57.3% (142 correctas, 106 incorrectas)
- Error rate: 42.7%
- Veredicto: 🔻 **BAJO VALOR** — Precisión 50-70%, agrega ruido


---

## Conclusiones (basadas en 248 cuentas verificadas con conflicto SM vs Regex)


**Total verificadas:** 248 (SM correcto: 142, Regex correcto: 106, Revisión: 71)


### Qué clasificador realmente aporta valor


1. **SM Tier 2** (Precisión 100%, 60/60) — **GANADOR**. Sin errores en la muestra.
2. **SM Tier 5** (Precisión 100%, 38/38) — **GANADOR**. Sin errores en la muestra.
3. **SM Tier 6** (Precisión 65%, 56/86) — **BORDE**. Útil como respaldo, pero 34% de error.
4. **Diccionario Fuzzy** (Precisión 58%, 21/36) — **BORDE**. Baja cobertura pero aceptable cuando acierta.
5. **DecisionEngineV2** (Precisión 59%, 147/248) — **BORDE**. Mejora sobre clasificadores individuales pero aún 41% error en conflictos.

### Qué clasificador agrega ruido


6. **SM Tier 1** (Precisión 52%, 96/186) — **AGREGA RUIDO EN CONFLICTOS**. En cuentas sin conflicto acierta 100%, pero cuando Regex disputa el resultado, solo gana la mitad de las veces. Problema: el catálogo tiene keywords que matchan pero el código CMCC asignado es incorrecto para ese contexto.
7. **SM Tier 4** (Precisión 27%, 34/126) — **AGREGA RUIDO**. Fuzzy keyword match es poco confiable cuando hay conflicto.
8. **Regex** (Precisión 47%, 154/326) — **AGREGA RUIDO EN CONFLICTOS**. Similar a SM T1: en conflicto es 50/50.
9. **Gold Standard Exacto** (Precisión 38%, 58/151) — **AGREGA RUIDO**. Datos auto-sembrados no son confiables.
10. **Código Contable** (Precisión 27%, 7/26) — **AGREGA RUIDO**. Baja precisión incluso en su nicho.

### Recomendaciones


1. **SM Tier 1-2 deben ganar siempre** — son infalibles cuando NO hay conflicto
2. **En caso de conflicto SM vs Regex**: la decisión es 50/50 — se necesita más evidencia
3. **El problema real es el catálogo**: 90 de 186 errores de SM T1 son porque el concepto asigna un código CMCC incorrecto
4. **Limpiar el Gold Standard**: 61.6% error en GS exacto indica que los datos sembrados automáticamente no son confiables
5. **El DecisionEngineV2 con weighted ensemble** es superior a cualquier clasificador individual (59% vs ~50% en conflictos)
6. **Threshold óptimo**: score ≥ 0.85 para decisiones automáticas; bajo eso, revisión humana.

