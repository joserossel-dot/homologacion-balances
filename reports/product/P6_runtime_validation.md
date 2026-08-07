# P6 — Validación del Runtime Depurado (Knowledge Incremental)

**Fecha:** 2026-08-05T17:06:32+00:00
**Estado:** ✅ Validado — 0 regresiones, gold_standard.db byte-idéntica.
**Archivos afectados (controlados):**
- `gold_standard_runtime.db` (runtime) — migración + desactivación de 11 claves.
- `gold_standard/runtime_manager.py` — columna `activa`, filtro de búsqueda, métodos `set_active/deactivate/activate`, checksum con `activa`.
- **`gold_standard.db` NO se tocó** (checksum original confirmado).

---

## 1) Runtime ANTES de la depuración

- Conocimiento en `runtime_gold`: **107 claves** (todas activas por defecto tras la promoción P6_first_population).
- El runtime **competía** con el gold: al buscar, cualquier clave runtime con colisión exacta/fuzzy (≥92) se resolvía **antes** que el gold, pudiendo anular un código gold correcto.
- **Impacto medido (shadow con 107 claves):**
  - Regresiones (gold resolvía correctamente y runtime lo cambia): **106**
  - Cuentas nuevas resueltas: **364**

## 2) Runtime DESPUÉS de la depuración

- Se añadió la columna `activa` (`runtime_gold.activa`), conservando **los 107 registros** (nada se elimina).
- **11 claves** marcadas `activa=0` (INACTIVE) con evento `DISABLE` auditable en `promotion_history`.
- **96 claves activas** (`activa=1`): participan en las búsquedas.
- `search_runtime` solo consulta `WHERE activa = 1`.
- **Impacto medido (shadow con 96 claves activas):**
  - Regresiones: **0** ✅
  - Cuentas nuevas (None → código): **336** ✅ (integridad del dato: las APP de cuentas se conservan; baja respecto a 364 porque se retiraron claves B/D que aportaban cobertura)

## 3) Claves ACTIVAS (96) — Conocimiento Incremental (categoría A)

| normalized | código | nombre_cuenta |
|---|---|--|
| `caja` | `AC.01` | `Caja` |
| `security` | `AC.01` | `Security` |
| `safra national bank of n york` | `AC.01` | `Safra National Bank of N. York` |
| `fondo de inversiones` | `AC.02` | `Fondo de Inversiones` |
| `fondo de inversion cap 12 usd` | `AC.02` | `Fondo de Inversion Cap.12 USD` |
| `101 1101 anticipo proveedores` | `AC.08` | `101.1101 Anticipo Proveedores` |
| `4 02 1201 diferencias de cambio perdida s72` | `ER.15` | `4.02,1201 Diferencias de cambio Perdida s72` |
| `patentes y contribuciones` | `ER.04` | `PATENTES Y CONTRIBUCIONES` |
| `multas y costas` | `ER.04` | `MULTAS Y COSTAS` |
| `iva no recuperable` | `ER.04` | `IVA NO RECUPERABLE` |
| `inscripciones` | `ER.01` | `INSCRIPCIONES` |
| `renovacion credenciales` | `ER.01` | `RENOVACION CREDENCIALES` |
| `ingresos por actividades regional` | `ER.01` | `INGRESOS POR ACTIVIDADES REGIONAL` |
| `arriendo departamentos` | `ER.01` | `ARRIENDO DEPARTAMENTOS` |
| `arriendo de oficinas` | `ER.01` | `ARRIENDO DE OFICINAS` |
| `ctas sociales colegio nacional` | `ER.01` | `CTAS SOCIALES COLEGIO NACIONAL` |
| `ingreso por donaciones` | `ER.13` | `INGRESO POR DONACIONES` |
| `aporte nestle` | `ER.13` | `APORTE NESTLE` |
| `auspicios` | `ER.13` | `AUSPICIOS` |
| `gastos por depreciacion` | `ER.07` | `GASTOS POR DEPRECIACION` |
| `ingresos capacitaciones` | `ER.01` | `INGRESOS CAPACITACIONES` |
| `1 01 01 10 fondos por rendir` | `AC.08` | `1.01.01.10 Fondos por Rendir` |
| `dapitau` | `AC.02` | `DAPITAU` |
| `exisitencias deteccion` | `AC.05` | `Exisitencias Deteccion` |
| `y 1 01 09 19 plan moniterio gc track` | `AC.08` | `y 1,01.09,19 — Plan Moniterio GC-TRACK` |
| `e 1 02 04 03 herramientas en consignacion` | `ANC.01` | `É 1.02.04,03 — Herramientas en Consignacion` |
| `a 1 02 03 03 vehiculos` | `ANC.01` | `a 1.02.03.03 — Vehículos` |
| `n 1 02 03 04 equipos de comunicacion` | `ANC.01` | `Ñ 1.02.03.04 Equipos de Comunicacion` |
| `1 02 06 01 depreciacion acumulada` | `ANC.01` | `, 1.02.06.01 Depreciación Acumulada` |
| `2 01 01 04 tarjeta de credito banco ch` | `AC.07` | `2.01.01,.04 Tarjeta de Credito Banco Ch` |
| `2 01 07 04 cheques por pagar` | `PC.01` | `2.01.07.04 Cheques por Pagar` |
| `a 3 02 01 01 intereses ganados` | `ER.12` | `a 3.02.01.01 Intereses Ganados` |
| `b 3 02 03 01 utilidad en venta de activo fijo` | `ER.13` | `“b 3.02.03.01 Utilidad en venta de Activo Fijo` |
| `401 03 01 honorarios contable computacional legal` | `ER.04` | `, 401.03.01 Honorarios Contable, Computacional, Legal` |
| `bci` | `PC.02` | `BCI` |
| `banco estado` | `AC.01` | `Banco Estado` |
| `bco scotiabak` | `AC.01` | `Bco. Scotiabak` |
| `banco chile dolares chile` | `AC.01` | `Banco Chile Dolares Chile` |
| `corpbanca dolares chile` | `AC.01` | `CorpBanca Dolares Chile¿?` |
| `citibank dolares miami` | `AC.01` | `Citibank Dolares Miami` |
| `bci dolares chile` | `AC.01` | `BCI Dolares Chile` |
| `bci euros chile` | `AC.01` | `BCI Euros Chile` |
| `corpbanca dolares n york` | `PC.02` | `Corpbanca Dolares N. York` |
| `bco scotiabank dolares` | `PC.02` | `Bco. Scotiabank Dolares` |
| `banco itau dolares chile` | `PC.02` | `Banco Itaú Dolares Chile` |
| `deposito a plazo usd chile` | `AC.02` | `Deposito a Plazo USD/Chile` |
| `clientes extranjeros` | `AC.03` | `Clientes Extranjeros` |
| `anticipos proveedores temp` | `AC.07` | `Anticipos Proveedores Temp` |
| `materiales insumo campo` | `AC.05` | `Materiales Insumo Campo` |
| `materiales de exportacion` | `AC.05` | `Materiales de Exportacion` |
| `hectarias en formacion` | `AC.09` | `Hectarias en Formacion` |
| `credito 4 activo fijo` | `AC.08` | `Crédito 4% Activo Fijo` |
| `vehiculos en leasing` | `ANC.01` | `Vehículos en Leasing` |
| `maquinarias en leasing` | `ANC.01` | `Maquinarias en Leasing` |
| `depreciacion acumulada a leas` | `ANC.01` | `Depreciación Acumulada A. Leas` |
| `instalaciones en locales` | `ANC.01` | `Instalaciones en Locales` |
| `equipo de computacion` | `ANC.01` | `Equipo de Computación` |
| `software computacionales` | `ANC.03` | `Software Computacionales` |
| `plantacion uva de mesa` | `ANC.07` | `Plantacion Uva de Mesa` |
| `credito exportador en dolares` | `PC.02` | `Credito Exportador en Dolares` |
| `linea de credito bancaria` | `PC.02` | `Línea de Crédito Bancaria` |
| `proveedor nacional temporada` | `PC.01` | `Proveedor Nacional Temporada` |
| `facturas proveedor extranjero` | `PC.01` | `Facturas Proveedor Extranjero` |
| `letras por pagar m e` | `PC.01` | `Letras por Pagar M/E` |
| `empresas relacionadas en uf` | `ANC.05` | `Empresas Relacionadas en UF` |
| `gastos provisionados` | `PC.06` | `Gastos Provisionados` |
| `afp` | `PC.06` | `AFP` |
| `caja de compensacion` | `PC.06` | `Caja de Compensación` |
| `mutual de seguridad cchc` | `PC.06` | `Mutual de Seguridad CCHC` |
| `retencion prestamo solidario` | `PC.06` | `Retencion Prestamo Solidario` |
| `descuentos del personal` | `AC.07` | `Descuentos del Personal` |
| `cheques caducados` | `PC.08` | `Cheques Caducados` |
| `impuesto a la renta por pagar` | `PC.05` | `Impuesto a la Renta por Pagar` |
| `fruta de exportacion` | `ER.01` | `Fruta de Exportación` |
| `otras ventas` | `ER.01` | `Otras Ventas` |
| `costo de exportacion` | `ER.02` | `Costo de Exportacion` |
| `costos frigorifico` | `ER.02` | `Costos Frigorifico` |
| `costo explotacion campo` | `ER.02` | `Costo Explotacion Campo` |
| `creditos exportadores pae` | `__EXCLUIR__` | `Créditos Exportadores (PAE)` |
| `provision insumos` | `__EXCLUIR__` | `Provision Insumos` |
| `distr facturas campo frio` | `__EXCLUIR__` | `Distr. Facturas Campo-Frio` |
| `gastos mantencion act fijo` | `ER.04` | `Gastos Mantencion Act. Fijo` |
| `intereses creditos bancarios` | `ER.09` | `Intereses Créditos Bancarios` |
| `intereses bancarios pae` | `ER.09` | `Intereses Bancarios PAE` |
| `intereses pae temporada` | `ER.09` | `Intereses PAE Temporada` |
| `distribucion utilidades` | `PAT.03` | `Distribucion Utilidades` |
| `itau` | `AC.01` | `ITAU` |
| `remanente credito fiscal` | `AC.08` | `Remanente Crédito Fiscal` |
| `instituto prevision social` | `PC.06` | `Instituto Prevision Social` |
| `servicios frigorifico` | `ER.01` | `Servicios Frigorifico` |
| `costos operac frigorifico` | `ER.02` | `Costos Operac. Frigorifico` |
| `bcl` | `PC.02` | `BCl` |
| `anticipo honoranos` | `AC.08` | `Anticipo Honoraños` |
| `inventario animales vacuno` | `AC.05` | `Inventario Animales Vacuno` |
| `nogales` | `ANC.01` | `Nogales` |
| `facturas ganado` | `PC.01` | `Facturas Ganado` |

## 4) Claves DESACTIVADAS (11) — con justificación

| normalized | categoría | motivo |
|---|---|--|
| `provision vacaciones` | Redundante | gold la cubre con PC.06 (mismo código) |
| `impuesto unico trabajadores` | Redundante | gold la cubre con PC.05 (mismo código) |
| `anticipo honorarios` | Ambigua | colisión fuzzy AC.05->AC.07 |
| `anticipo proveedores` | Ambigua | colisión fuzzy AC.05->AC.07 |
| `linea de credito bango chile` | Redundante | gold la cubre con PC.02 (mismo código, typo) |
| `banco santarder` | Redundante | gold la cubre con AC.01 (mismo código, typo) |
| `anticipos de proveedores` | Ambigua | colisión fuzzy AC.05->AC.07 |
| `anticipo cliente us` | Redundante | gold la cubre con PC.08 (mismo código) |
| `diferencia de cambio mn` | Conflictiva | gold ER.09 vs runtime ER.15 |
| `diferencia de cambio me` | Conflictiva | gold ER.09 vs runtime ER.15 |
| `lva credito fiscal` | Conflictiva | gold AC.07 vs runtime AC.08 |

## 5) Cobertura obtenida y hits esperados

Medido sobre el pipeline real (baseline 299 PDFs, 23.292 apariciones de cuentas, 9.942 únicas normalizadas) con las **96 claves activas**:

| Métrica | Valor |
|---|---|
| Runtime Exact Hits esperados | **297** |
| Runtime Fuzzy Hits esperados | **185** |
| Cuentas NUEVAS (antes sin código gold) | **336** apariciones / **123** únicas |
| Regresiones | **0** |
| gold_standard.db byte-idéntica | ✅ SHA-256 `0a60334706d950c91c442c65fb0ad8cb103bf7b93bea861c085d4ed0bb3d54c6` |

Nuevas por código: {"AC.01": 20, "AC.05": 8, "AC.08": 12, "ER.15": 1, "ER.04": 5, "AC.02": 7, "ANC.01": 13, "AC.07": 3, "PC.01": 5, "ER.12": 1, "ER.13": 1, "PC.06": 14, "ER.01": 5, "ER.02": 9, "PAT.03": 2, "ER.09": 3, "PC.02": 12, "ANC.05": 2, "AC.09": 1, "PC.05": 2, "AC.03": 2, "ANC.07": 2, "PC.08": 1, "__EXCLUIR__": 2}

## 6) Confirmación: el runtime ya NO compite con el gold

- **0 regresiones**: ninguna cuenta que el gold resolvía correctamente cambió de código.
- Las **96 claves activas son incremental** (sin equivalente exacto ni fuzzy ≥92 en gold).
- El gold mantiene **prioridad total**: en caso de que `search_runtime` no resuelva (o resuelva igual que gold), gana el gold.
- El runtime **complementa** el gold: solo aporta código a cuentas que el gold dejaba sin clasificar (`None → código`).

**Conclusión:** el runtime actúa exclusivamente como **conocimiento incremental complementario**. No reemplaza ni contradice al gold.

## 7) Auditoría

- `gold_standard_runtime.db` conserva **107 registros** (0 eliminados) — **107/107 intacto**.
- `promotion_history`: **107 PROMOTE + 11 DISABLE** (total 118), cada DISABLE con state=INACTIVE y comentario.
- `metadata.checksum` actualizado: refleja el estado nuevo (incluye `activa`).
- Backup pre-depuración: `/tmp/backup_runtime_pre_depuracion/runtime_pre_depuracion.db`; hash previo `67e65b85…`.
