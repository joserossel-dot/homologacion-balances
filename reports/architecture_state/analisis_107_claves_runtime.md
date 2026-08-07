# Análisis de las 107 claves promovidas al Runtime (gold_standard_runtime.db)

**Fecha:** 2026-08-05 | **Fuentes:** `gold_standard_runtime.db` (107 claves), `gold_standard.db`, `baseline_results.json` (9.574 cuentas únicas normalizadas).
**Objetivo:** redefinir el runtime para que contenga **exclusivamente conocimiento incremental** (complementar, nunca reemplazar ni competir con el gold). Ninguna base de datos fue modificada durante este análisis.

## Resumen por categoría

| Categoría | Definición | Claves | Cobertura nueva | Regresiones |
|---|---|---|---|---|
| **A) Incremental** | Sin clave equivalente (exacta o fuzzy ≥92) en gold. Aporta conocimiento nuevo. | **96** | 336 | 0 |
| **B) Redundante** | Existe en gold con el **mismo** código. No aporta valor. | **5** | 3 | 0 |
| **C) Conflictiva** | Existe en gold con código **distinto**. Nunca activar automáticamente. | **3** | 0 | 107 |
| **D) Ambigua** | Producen colisiones fuzzy con **múltiples cuentas** o cambios de código reales. Excluir. | **3** | 25 | 13 |
| **Total** | | **107** | 364 | 120 |

**Impacto global observado si el runtime estuviera activo con las 107 claves:** +364 cuentas nuevas resueltas (None→código) y **120 regresiones** (código gold correcto → otro código).

---

## A) INCREMENTAL — 96 claves (mantener)
Sin equivalente exacto ni fuzzy ≥92 en gold. Cobertura nueva: +336 cuentas, regresiones: 0.
Propuesta: **conservar en el runtime tal cual.**

| `caja`	| `AC.01`	| 65	| None->AC.01→65	| —	|
| `costo de exportacion`	| `ER.02`	| 19	| None->ER.02→19	| —	|
| `afp`	| `PC.06`	| 18	| None->PC.06→18	| —	|
| `linea de credito bancaria`	| `PC.02`	| 14	| None->PC.02→14	| —	|
| `banco estado`	| `AC.01`	| 13	| None->AC.01→13	| —	|
| `caja de compensacion`	| `PC.06`	| 13	| None->PC.06→13	| —	|
| `mutual de seguridad cchc`	| `PC.06`	| 13	| None->PC.06→13	| —	|
| `equipo de computacion`	| `ANC.01`	| 11	| None->ANC.01→11	| —	|
| `otras ventas`	| `ER.01`	| 10	| None->ER.01→10	| —	|
| `remanente credito fiscal`	| `AC.08`	| 9	| None->AC.08→9	| —	|
| `credito 4 activo fijo`	| `AC.08`	| 6	| None->AC.08→6	| —	|
| `descuentos del personal`	| `AC.07`	| 6	| None->AC.07→6	| —	|
| `intereses creditos bancarios`	| `ER.09`	| 6	| None->ER.09→6	| —	|
| `retencion prestamo solidario`	| `PC.06`	| 5	| None->PC.06→5	| —	|
| `bcl`	| `PC.02`	| 4	| None->PC.02→4	| —	|
| `costos frigorifico`	| `ER.02`	| 4	| None->ER.02→4	| —	|
| `fondo de inversiones`	| `AC.02`	| 4	| None->AC.02→4	| —	|
| `anticipo honoranos`	| `AC.08`	| 3	| None->AC.08→3	| —	|
| `cheques caducados`	| `PC.08`	| 3	| None->PC.08→3	| —	|
| `citibank dolares miami`	| `AC.01`	| 3	| None->AC.01→3	| —	|
| `deposito a plazo usd chile`	| `AC.02`	| 3	| None->AC.02→3	| —	|
| `empresas relacionadas en uf`	| `ANC.05`	| 3	| None->ANC.05→3	| —	|
| `gastos provisionados`	| `PC.06`	| 3	| None->PC.06→3	| —	|
| `hectarias en formacion`	| `AC.09`	| 3	| None->AC.09→3	| —	|
| `intereses bancarios pae`	| `ER.09`	| 3	| None->ER.09→3	| —	|
| `inventario animales vacuno`	| `AC.05`	| 3	| None->AC.05→3	| —	|
| `materiales de exportacion`	| `AC.05`	| 3	| None->AC.05→3	| —	|
| `materiales insumo campo`	| `AC.05`	| 3	| None->AC.05→3	| —	|
| `nogales`	| `ANC.01`	| 3	| None->ANC.01→3	| —	|
| `patentes y contribuciones`	| `ER.04`	| 3	| None->ER.04→3	| —	|
| `plantacion uva de mesa`	| `ANC.07`	| 3	| None->ANC.07→3	| —	|
| `security`	| `AC.01`	| 3	| None->AC.01→3	| —	|
| `servicios frigorifico`	| `ER.01`	| 3	| None->ER.01→3	| —	|
| `arriendo de oficinas`	| `ER.01`	| 2	| None->ER.01→2	| —	|
| `banco chile dolares chile`	| `AC.01`	| 2	| None->AC.01→2	| —	|
| `banco itau dolares chile`	| `PC.02`	| 2	| None->PC.02→2	| —	|
| `bci`	| `PC.02`	| 2	| None->PC.02→2	| —	|
| `bci dolares chile`	| `AC.01`	| 2	| None->AC.01→2	| —	|
| `bci euros chile`	| `AC.01`	| 2	| None->AC.01→2	| —	|
| `clientes extranjeros`	| `AC.03`	| 2	| None->AC.03→2	| —	|
| `costo explotacion campo`	| `ER.02`	| 2	| None->ER.02→2	| —	|
| `costos operac frigorifico`	| `ER.02`	| 2	| None->ER.02→2	| —	|
| `depreciacion acumulada a leas`	| `ANC.01`	| 2	| None->ANC.01→2	| —	|
| `distribucion utilidades`	| `PAT.03`	| 2	| None->PAT.03→2	| —	|
| `exisitencias deteccion`	| `AC.05`	| 2	| None->AC.05→2	| —	|
| `facturas ganado`	| `PC.01`	| 2	| None->PC.01→2	| —	|
| `facturas proveedor extranjero`	| `PC.01`	| 2	| None->PC.01→2	| —	|
| `fruta de exportacion`	| `ER.01`	| 2	| None->ER.01→2	| —	|
| `impuesto a la renta por pagar`	| `PC.05`	| 2	| None->PC.05→2	| —	|
| `itau`	| `AC.01`	| 2	| None->AC.01→2	| —	|
| `letras por pagar m e`	| `PC.01`	| 2	| None->PC.01→2	| —	|
| `maquinarias en leasing`	| `ANC.01`	| 2	| None->ANC.01→2	| —	|
| `safra national bank of n york`	| `AC.01`	| 2	| None->AC.01→2	| —	|
| `vehiculos en leasing`	| `ANC.01`	| 2	| None->ANC.01→2	| —	|
| `1 01 01 10 fondos por rendir`	| `AC.08`	| 1	| None->AC.08→1	| —	|
| `1 02 06 01 depreciacion acumulada`	| `ANC.01`	| 1	| None->ANC.01→1	| —	|
| `101 1101 anticipo proveedores`	| `AC.08`	| 1	| None->AC.08→1	| —	|
| `2 01 01 04 tarjeta de credito banco ch`	| `AC.07`	| 1	| None->AC.07→1	| —	|
| `2 01 07 04 cheques por pagar`	| `PC.01`	| 1	| None->PC.01→1	| —	|
| `4 02 1201 diferencias de cambio perdida s72`	| `ER.15`	| 1	| None->ER.15→1	| —	|
| `401 03 01 honorarios contable computacional legal`	| `ER.04`	| 1	| None->ER.04→1	| —	|
| `a 1 02 03 03 vehiculos`	| `ANC.01`	| 1	| None->ANC.01→1	| —	|
| `a 3 02 01 01 intereses ganados`	| `ER.12`	| 1	| None->ER.12→1	| —	|
| `b 3 02 03 01 utilidad en venta de activo fijo`	| `ER.13`	| 1	| None->ER.13→1	| —	|
| `bco scotiabak`	| `AC.01`	| 1	| None->AC.01→1	| —	|
| `bco scotiabank dolares`	| `PC.02`	| 1	| None->PC.02→1	| —	|
| `corpbanca dolares chile`	| `AC.01`	| 1	| None->AC.01→1	| —	|
| `corpbanca dolares n york`	| `PC.02`	| 1	| None->PC.02→1	| —	|
| `credito exportador en dolares`	| `PC.02`	| 1	| None->PC.02→1	| —	|
| `creditos exportadores pae`	| `__EXCLUIR__`	| 1	| None->__EXCLUIR__→1	| —	|
| `dapitau`	| `AC.02`	| 1	| None->AC.02→1	| —	|
| `distr facturas campo frio`	| `__EXCLUIR__`	| 1	| None->__EXCLUIR__→1	| —	|
| `e 1 02 04 03 herramientas en consignacion`	| `ANC.01`	| 1	| None->ANC.01→1	| —	|
| `gastos mantencion act fijo`	| `ER.04`	| 1	| None->ER.04→1	| —	|
| `instituto prevision social`	| `PC.06`	| 1	| None->PC.06→1	| —	|
| `intereses pae temporada`	| `ER.09`	| 1	| None->ER.09→1	| —	|
| `iva no recuperable`	| `ER.04`	| 1	| None->ER.04→1	| —	|
| `n 1 02 03 04 equipos de comunicacion`	| `ANC.01`	| 1	| None->ANC.01→1	| —	|
| `proveedor nacional temporada`	| `PC.01`	| 1	| None->PC.01→1	| —	|
| `y 1 01 09 19 plan moniterio gc track`	| `AC.08`	| 1	| None->AC.08→1	| —	|
| `anticipos proveedores temp`	| `AC.07`	| 0	| —	| —	|
| `aporte nestle`	| `ER.13`	| 0	| —	| —	|
| `arriendo departamentos`	| `ER.01`	| 0	| —	| —	|
| `auspicios`	| `ER.13`	| 0	| —	| —	|
| `ctas sociales colegio nacional`	| `ER.01`	| 0	| —	| —	|
| `fondo de inversion cap 12 usd`	| `AC.02`	| 0	| —	| —	|
| `gastos por depreciacion`	| `ER.07`	| 0	| —	| —	|
| `ingreso por donaciones`	| `ER.13`	| 0	| —	| —	|
| `ingresos capacitaciones`	| `ER.01`	| 0	| —	| —	|
| `ingresos por actividades regional`	| `ER.01`	| 0	| —	| —	|
| `inscripciones`	| `ER.01`	| 0	| —	| —	|
| `instalaciones en locales`	| `ANC.01`	| 0	| —	| —	|
| `multas y costas`	| `ER.04`	| 0	| —	| —	|
| `provision insumos`	| `__EXCLUIR__`	| 0	| —	| —	|
| `renovacion credenciales`	| `ER.01`	| 0	| —	| —	|
| `software computacionales`	| `ANC.03`	| 0	| —	| —	|

---

## B) REDUNDANTE — 5 claves (eliminar)
Existen en gold (exacto o fuzzy ≥92) con el **mismo** código. No aportan valor, solo duplican.
Propuesta: **eliminar del runtime** (el gold ya las cubre).

| `banco santarder`	| `AC.01`	| 32	| None->AC.01→1	| banco santander(AC.01,93.3)	|
| `impuesto unico trabajadores`	| `PC.05`	| 12	| —	| impuesto único trabajadores(PC.05,96.3)	|
| `anticipo cliente us`	| `PC.08`	| 6	| None->PC.08→2	| anticipo clientes(PC.08,94.4)	|
| `linea de credito bango chile`	| `PC.02`	| 6	| —	| linea de credito banco chile(PC.02,96.4)	|
| `provision vacaciones`	| `PC.06`	| 4	| —	| provisión vacaciones(PC.06,95.0)	|

---

## C) CONFLICTIVA — 3 claves (nunca activar)
Existen en gold con código **distinto**. Si se activan, anulan un código gold correcto.
Propuesta: **eliminar / excluir permanentemente** del runtime. Son las únicas que causan regresión pura 1→1.

| `lva credito fiscal`	| `AC.08`	| 37	| AC.07->AC.08→37	| iva credito fiscal(AC.07,94.4)	|
| `diferencia de cambio me`	| `ER.15`	| 35	| ER.09->ER.15→35	| diferencia de cambio(ER.09,93.0)	|
| `diferencia de cambio mn`	| `ER.15`	| 35	| ER.09->ER.15→35	| diferencia de cambio(ER.09,93.0)	|

---

## D) AMBIGUA — 3 claves (excluir)
Producen colisiones fuzzy con múltiples cuentas o cambios de código reales (AC.05→AC.07) sin umbral ≥92 exacto, generando ambigüedad no controlada.
Propuesta: **excluir del runtime** y reevaluar manualmente contra el criterio del analista.

| `anticipo proveedores`	| `AC.07`	| 49	| AC.05->AC.07→4; None->AC.07→2	| anticipo a proveedores(AC.07,95.2); anticipos a proveedores(AC.05,93.0)	|
| `anticipo honorarios`	| `AC.07`	| 21	| None->AC.07→15; AC.05->AC.07→6	| —	|
| `anticipos de proveedores`	| `AC.07`	| 11	| None->AC.07→8; AC.05->AC.07→3	| —	|

---

## Propuesta de acción final
1. **Mantener** las **96 claves A** (incremental) → runtime queda con +364−duplicados... *(ver nota)*.
2. **Eliminar** las **5 B** (redundantes) y las **3 C** (conflictivas) y las **3 D** (ambiguas) — 11 claves en total → elimina las **120 regresiones**.
3. Resultado: runtime final ≈ **96 claves**, todas incrementales, **0 regresiones**, que **complementan** al gold añadiendo cobertura útil.

> Nota de impacto: al quitar las 3 D se retiran también sus cuentas None→código (23 cuentas: 15+8). Tras la depuración el runtime añadiría cobertura **nueva neta** (None→código) sin tocar jamás un código gold ya resuelto.
