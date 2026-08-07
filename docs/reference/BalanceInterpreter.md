# BalanceInterpreter

> Archivo: `interpreters/balance_interpreter.py`
> Clase: `BalanceInterpreter`

## Propósito

Determina la **naturaleza** de cada cuenta del balance (Activo/Pasivo/
Pérdida/Ganancia) y calcula el **monto de clasificación** con signo correcto,
sirviendo de puente entre el raw del parser y la clasificación.

## Responsabilidad

- Interpretar el monto y su naturaleza a partir de una `CuentaRaw`.
- Producir un `AccountBalance` con `classification_amount` listo para
  clasificación por código y reglas R1-R5.

## Métodos y comportamiento

- `interpret(cuenta: CuentaRaw) -> AccountBalance` — crea el balance a partir
  de código, nombre y origen de columna.
- `classify_amount(monto: float | None, origen_columna: OrigenColumna) -> tuple[nature, amount]`:
  - `monto is None` → `(UNKNOWN, None)`.
  - Mapeo origen→naturaleza:
    - `ACTIVO → (ACTIVO, +monto)`
    - `PASIVO → (PASIVO, +monto)`
    - `PERDIDA → (PERDIDA, +monto)`
    - `GANANCIA → (GANANCIA, +monto)`
    - `DEUDOR → (ACTIVO, +monto)`
    - `ACREEDOR → (PASIVO, +monto)`
    - `DESCONOCIDO → (UNKNOWN, monto)` (naturaleza indeterminada)
- `is_asset(account: AccountBalance) -> bool`, `is_liability(...)`,
  `is_loss(...)`, `is_gain(...)` — conveniencias sobre `nature`.
- `get_nature_label(nature) -> str` — label humano.
- `as_string(account: AccountBalance) -> str` — resumen legible.
- `requires_classification(account: AccountBalance) -> bool` — `True` si la
  naturaleza es `UNKNOWN` (no se puede inferir el signo del monto).

## Naturaleza (`AccountNature`, en `models.py`)

`ASSET`, `LIABILITY`, `LOSS`, `PROFIT`, `UNKNOWN`.

## Salida

`AccountBalance` (`models.py`):

```
account_code, account_name, nature, classification_amount,
column_type (extra)
```

## Dependencias

`models.py` (`AccountBalance`, `AccountNature`, `OrigenColumna`),
`parser_universal.py` (`CuentaRaw`, `OrigenColumna`).

## Quién lo utiliza

- `pipeline/homologation_pipeline.py` (`_classify_account` y `process()`).
- `app_validacion.py` (flujo V1 legado).
- `validation/runner.py`.

## Riesgos técnicos

- La naturaleza depende enteramente del `origen_columna` que asigne el
  parser; si el parser no detecta columna (DESCONOCIDO), la cuenta queda
  `UNKNOWN` y `classification_amount` pierde el signo → afecta validación
  de ecuación y subtotales.
- El monto se mantiene con el signo de la columna (+monto); la dirección
  (débito/crédito) no se rastrea explícitamente.

## Posibles mejoras futuras

- Inferir naturaleza por nombre (heurística) cuando `origen_columna` sea
  desconocido.
- Distinguir monto débito vs crédito explícitamente en lugar de confiar en
  el signo de la columna.
