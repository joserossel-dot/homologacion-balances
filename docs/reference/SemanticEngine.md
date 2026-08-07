# SemanticEngine

> Archivo: `semantic/semantic_engine.py` (30 líneas) — clase `SemanticEngine`
> Reglas: `semantic/semantic_rules.py` (244 líneas)
> Modelos: `semantic/semantic_account.py` (`SemanticAccount`),
> `semantic/semantic_context.py` (`SemanticContext`)

## Propósito

Anota cada cuenta con **metadata semántica** (tipo, estado financiero,
naturaleza económica, presentación, lado esperado, categoría padre) mediante
reglas basadas en contexto (keywords + columna + naturaleza). Es una capa de
"conocimiento" complementaria a la clasificación de código; **no modifica el
código homologado** — su resultado solo se reporta.

## Responsabilidad

Aplicar reglas semánticas priorizadas sobre un `AccountBalance` y producir un
`SemanticAccount` con la metadata y confianza del match.

## Clase

### `SemanticEngine` (`semantic_engine.py:9-30`)

- `__init__(rules=None)` (`:10-11`): ordena las reglas por `priority`
  ascendente; si `rules=None`, usa `build_rules()` (las 10 reglas globales).
- `interpret(account: AccountBalance) -> SemanticAccount` (`:13-30`):
  - Crea `SemanticContext.from_account(account)` (infiere `source_column` y
    `balance_side` desde los montos del balance).
  - Evalúa reglas en orden de prioridad; devuelve la **primera** que
    devuelva resultado (`first-match-wins`).
  - Si ninguna aplica → `SemanticAccount` con `semantic_type="unknown"`,
    `matched_rule="no_match"`, `confidence=0.0`, observación
    "No se aplicó ninguna regla semántica".

## Reglas globales (`semantic_rules.py:87-240`)

| Regla | Prioridad | Keywords requeridas | Keywords prohibidas | Columna | Tipo resultante |
|---|---|---|---|---|---|
| `depreciacion_acumulada` | 10 | deprec* + acumul* | ejercicio | activo/pasivo | contra_asset |
| `amortizacion_acumulada` | 11 | amortiz* + acumul* | ejercicio | activo/pasivo | contra_asset |
| `depreciacion_del_ejercicio` | 20 | deprec* + ejercicio | acumul* | perdida | expense |
| `amortizacion_del_ejercicio` | 21 | amortiz* + ejercicio | acumul* | perdida | expense |
| `iva_credito_fiscal` | 30 | iva + crédito | débito | activo | asset |
| `iva_debito_fiscal` | 31 | iva + débito | crédito | pasivo | liability |
| `provision_vacaciones` | 40 | provisión + vacaciones | gasto | pasivo | liability |
| `gasto_por_vacaciones` | 41 | gasto + vacaciones | provisión | perdida | expense |
| `anticipo_proveedores` | 50 | anticipo* + proveedores | clientes | activo | asset |
| `anticipos_de_clientes` | 51 | anticipo* + clientes | proveedores | pasivo | liability |

Nota: `_context_rule` (`:21-84`) filtra por keywords (cada grupo con OR
interno, todos los grupos requeridos), forbidden, columna aceptada,
naturaleza, lado del balance y prefijo de código; la confianza final es
`clamp(base_confidence + modifier, 0, 1)` (default base 0.95).

## Modelos

### `SemanticAccount` (`semantic_account.py:7-32`)

`semantic_type, financial_statement, economic_nature, presentation,
expected_side, parent_category, contra_account_type, confidence,
matched_rule, observations` + `to_dict()`.

### `SemanticContext` (`semantic_context.py:9-59`)

`account, source_column, balance_side`; infiere `source_column`
(activo/pasivo/perdida/ganancia/deudor/acreedor) y `balance_side`
(deudor/acreedor) desde `account.amounts`; helpers `code_first_digit()`,
`code_prefix(length)`.

## Salida

`SemanticAccount`. En el pipeline se guarda en cada cuenta como
`semantic_result` (`homologation_pipeline.py:517, 559-566`) y contribuye a
los contadores `semantic_total/matches/unknown/confidence_avg` del summary.

## Dependencias

- `models/account_balance.py` (`AccountBalance`), `models/account_nature.py`.
- `semantic/` interno (account, context, rules).

## Quién lo utiliza

- `pipeline/homologation_pipeline.py` (`SemanticEngine.interpret` por cuenta).
- `adapters/kb_adapter.py` (V2, `:123`).
- `docs/ADR-001-Semantic-Architecture.md` documenta su arquitectura.
- `scripts/` de benchmark semántico.

## Riesgos técnicos

- Reglas con **keywords en español hardcodeadas** (depreciación, iva,
  vacaciones, anticipos, proveedores/clientes); no cubre otras categorías.
- `_infer_source_column` depende de `account.amounts` (campos por columna);
  si el parser no detectó montos por columna, `source_column="unknown"` y
  reglas con `acceptable_columns` fallan.
- Es metadata de reporte: **no participa** en la decisión del código final.
- El contenido es conocimiento de negocio **embebido en código**, no
  configurable.

## Posibles mejoras futuras

- Externalizar las reglas (JSON/YAML) o alimentarlas desde el Knowledge Base.
- Conectar `semantic_type` con la validación de cobertura semántica del V2.

## Diferencia con `SemanticMatcher`

Existen dos componentes "semánticos" distintos en el proyecto:

- **`SemanticEngine`** (este documento): reglas de contexto por keywords;
  solo produce metadata de reporte; se ejecuta **siempre** en V1.
- **`SemanticMatcher`** (`semantic/matcher.py`, ver
  `docs/reference/HomologationPipeline.md` y `docs/modules/semantic_engine.md`):
  matcher por catálogo de conceptos (`knowledge/concept_catalog.json`) con 6
  tiers, que **sí participa en la clasificación** pero solo cuando
  `ENABLE_SEMANTIC_MATCHER=True` (default OFF). Independiente del pipeline.
