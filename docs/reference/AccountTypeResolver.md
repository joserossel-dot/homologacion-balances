# AccountTypeResolver

> Archivo: `parsers/account_type_resolver.py`
> Clase: `AccountTypeResolver`

## Propósito

Resuelve la **familia de cuentas** (ACTIVO/PASIVO/PATRIMONIO/PERDIDA/
GANANCIA) de una cuenta del balance en función de su **código** (prefijo del
catálogo), para validar que el código homologado sea coherente con el tipo.

## Responsabilidad

- Mapear el origen del código (`ACTIVO`/`PASIVO`/`PERDIDA`/`GANANCIA`/
  `OTRO`) al tipo de cuenta correcto usando el prefijo del código
  (p.ej. `1-01` → ACTIVO).
- Producir un `AccountTypeResult` con el tipo resuelto y su confianza.

## Clase

### `AccountTypeResolver` (`:4`)

Atributo de clase: `_ORIGEN_TO_TYPES` (`:11-16`):

```
ACTIVO    → [AccountType.ACTIVO]
PASIVO    → [AccountType.PASIVO]
PERDIDA   → [AccountType.PERDIDA]
GANANCIA  → [AccountType.GANANCIA]
OTRO      → [AccountType.ACTIVO, AccountType.PASIVO,
            AccountType.PATRIMONIO, AccountType.PERDIDA,
            AccountType.GANANCIA]  (todos menos ACTIVO_FIJO)
```

Método principal:

### `resolve_account_type(codigo: str, origen: str = "OTRO") -> AccountTypeResult` (`:18-39`)

```
codigo / tipo
    1-01..1-08 → ACTIVO
    1-09, 1-10 → ACTIVO_FIJO
    2-..        → PASIVO
    3-..        → PATRIMONIO
    4-..        → PERDIDA
    5-..        → GANANCIA
    prefijo NUM con guion → tipo por primer segmento
    COMPACTO sin guion → UNKNOWN (confianza baja)
    c.c. → UNKNOWN (confianza baja)
```

Devuelve `AccountTypeResult(resolved_type, confidence, details)` donde la
confianza es `0.95` si `codigo` y `origen` coinciden, `0.7` si solo el
código (origen OTRO o inconsistente), `0.3` si UNKNOWN.

### `AccountTypeResult` (`:40-57`)

```
codigo: str
origen: str
resolved_type: AccountType
confidence: float
details: dict[str, str]
  "resolved_type", "origen", "confidence", "message", "account_type_str"
```

### `AccountType` (`parsers/account_type.py`)

Enum de 6 valores: `ACTIVO`, `ACTIVO_FIJO`, `PASIVO`, `PATRIMONIO`,
`PERDIDA`, `GANANCIA`.

## Salida

`AccountTypeResult` con tipo + confianza. La confianza se compara contra
`ACCOUNT_TYPE_CONFIDENCE_THRESHOLD` (`0.7`) en los consumidores para decidir
si se activa.

## Dependencias

- `parsers/account_type.py` (`AccountType`).
- `models.py` (`AccountTypeResult`? — depende de importación; verificar).

## Quién lo utiliza

- `parser_universal.py:781-809` — tras parsear las líneas, si
  `ENABLE_ACCOUNT_TYPE_RESOLVER` o el contexto es confiable
  (`LAYOUT_CONFIDENCE_THRESHOLD`/`ACCOUNT_TYPE_CONFIDENCE_THRESHOLD`).
- `pipeline/homologation_pipeline.py` — vía `_is_code_allowed_for_tipo` y
  `_classify_account` (tipo_filtered).
- `adapters/parser_adapter.py` (tipo_cuenta en CuentaRaw).

## Riesgos técnicos

- Solo acepta códigos con guion (`1-..`, `2-..`, ...). Códigos compactos o
  sin código quedan UNKNOWN.
- Confianza por origen `OTRO` baja: con `origen="OTRO"` siempre devuelve
  `0.7` aunque el código sea inequívoco → resuelve, pero débil.
- `_ORIGEN_TO_TYPES` es un mapa a `AccountType` (familia), pero el parser
  trabaja con `OrigenColumna`; la conversión origen→tipo es aproximada.

## Posibles mejoras futuras

- Soportar códigos compactos y sin código.
- Aumentar confianza cuando el código es inequívoco aunque el origen sea
  OTRO.
- Unificar `AccountType` con `AccountNature` y `OrigenColumna`.
