# Auditoría de precisión de REGLAS_REGEX

**Total PDFs analizados:** 19
**Total cuentas con match regex:** 375
**Total cuentas únicas:** 304

## Resumen global

| Métrica | Valor |
|---------|-------|
| Patrones evaluados | 37 |
| Matches totales | 375 |
| Falsos positivos detectados | 91 |
| Precisión promedio | 78.8% |

## Ranking por impacto (total matches)

| # | Código | Patrón | Matches | FP | Precisión | Riesgo |
|---|--------|--------|---------|----|-----------|--------|
| 1 | ANC.01 | `\b(activo\s*fijo|propiedad(es)?\s*planta|maquinari...` | 46 | 16 | 65.2% | Medio |
| 2 | AC.03 | `\b(clientes?|deudore(s)?\s*por\s*venta|cuentas?\s*...` | 44 | 14 | 68.2% | Medio |
| 3 | AC.01 | `\b(caja\s*chica|caja\s*y\s*banco|efectivo\s*y\s*eq...` | 43 | 6 | 86.0% | Bajo |
| 4 | PC.06 | `\b(remuneracion(es)?|sueldo(s)?|vacaciones?|honora...` | 42 | 11 | 73.8% | Medio |
| 5 | PAT.01 | `\b(capital\s*(pagado|suscrito|social|propio)?|apor...` | 27 | 8 | 70.4% | Medio |
| 6 | PAT.04 | `\butilidad\s*del\s*(ejercicio|periodo|a[ñn]o)|resu...` | 21 | 8 | 61.9% | Medio |
| 7 | ER.01 | `\b(venta(s)?|ingreso(s)?\s*(por\s*venta|operaciona...` | 18 | 6 | 66.7% | Medio |
| 8 | AC.07 | `\b(iva\s*(credito|cf)|ppm|impuesto(s)?\s*por\s*rec...` | 14 | 2 | 85.7% | Bajo |
| 9 | ER.09 | `\bgasto(s)?\s*financiero(s)?|intere(s|ses)?\s*(pag...` | 14 | 0 | 100.0% | Bajo |
| 10 | PAT.03 | `\b(utilidad(es)?\s*(acumulada(s)?|retenida(s)?)|re...` | 11 | 4 | 63.6% | Medio |
| 11 | PC.03 | `\bleasing\s*(cp|corriente|corto)?\b...` | 10 | 2 | 80.0% | Medio |
| 12 | PC.01 | `\b(proveedor(es)?|acreedore(s)?\s*comercial|factur...` | 9 | 3 | 66.7% | Medio |
| 13 | ER.02 | `\bcosto(s)?\s*(de\s*)?(venta(s)?|explotacion|produ...` | 9 | 1 | 88.9% | Bajo |
| 14 | ANC.03 | `\b(intangible(s)?|goodwill|marca(s)?|patente(s)?|l...` | 8 | 1 | 87.5% | Bajo |
| 15 | PC.05 | `\b(iva\s*(debito|df)|impuesto(s)?\s*por\s*pagar|pr...` | 8 | 0 | 100.0% | Bajo |
| 16 | AC.05 | `\b(inventario(s)?|existencia(s)?|mercader[ií]a(s)?...` | 7 | 2 | 71.4% | Medio |
| 17 | PAT.02 | `\b(reserva(s)?(\s*legal)?|prima\s*de\s*emision)\b...` | 7 | 0 | 100.0% | Bajo |
| 18 | ER.04 | `\bgasto(s)?\s*(de\s*)?(administracion|general(es)?...` | 7 | 0 | 100.0% | Bajo |
| 19 | ER.07 | `\b(depreciacion|amortizacion)\b...` | 7 | 3 | 57.1% | Alto |
| 20 | ER.10 | `\bimpuesto\s*(a\s*la\s*renta|primera\s*categoria)\...` | 6 | 0 | 100.0% | Bajo |
| 21 | AC.02 | `\b(inversion(es)?\s*(corto\s*plazo|cp)|fondos?\s*m...` | 5 | 2 | 60.0% | Medio |
| 22 | PC.08 | `\b(anticipo(s)?\s*de\s*cliente(s)?|ingreso(s)?\s*(...` | 5 | 0 | 100.0% | Bajo |
| 23 | PNC.03 | `\b(bono(s)?|debenture(s)?)\b...` | 3 | 1 | 66.7% | Medio |
| 24 | AC.04 | `\b(documento(s)?\s*por\s*cobrar|letras?\s*(por|a)\...` | 2 | 1 | 50.0% | Alto |
| 25 | ER.11 | `\butilidad\s*neta|resultado\s*neto|net\s*income|ga...` | 2 | 0 | 100.0% | Bajo |

## Ranking por menor precisión

| # | Código | Patrón | Matches | FP | Precisión | Riesgo |
|---|--------|--------|---------|----|-----------|--------|
| 1 | AC.04 | `\b(documento(s)?\s*por\s*cobrar|letras?\s*(por|a)\...` | 2 | 1 | 50.0% | Alto |
| 2 | ER.07 | `\b(depreciacion|amortizacion)\b...` | 7 | 3 | 57.1% | Alto |
| 3 | AC.02 | `\b(inversion(es)?\s*(corto\s*plazo|cp)|fondos?\s*m...` | 5 | 2 | 60.0% | Medio |
| 4 | PAT.04 | `\butilidad\s*del\s*(ejercicio|periodo|a[ñn]o)|resu...` | 21 | 8 | 61.9% | Medio |
| 5 | PAT.03 | `\b(utilidad(es)?\s*(acumulada(s)?|retenida(s)?)|re...` | 11 | 4 | 63.6% | Medio |
| 6 | ANC.01 | `\b(activo\s*fijo|propiedad(es)?\s*planta|maquinari...` | 46 | 16 | 65.2% | Medio |
| 7 | PC.01 | `\b(proveedor(es)?|acreedore(s)?\s*comercial|factur...` | 9 | 3 | 66.7% | Medio |
| 8 | PNC.03 | `\b(bono(s)?|debenture(s)?)\b...` | 3 | 1 | 66.7% | Medio |
| 9 | ER.01 | `\b(venta(s)?|ingreso(s)?\s*(por\s*venta|operaciona...` | 18 | 6 | 66.7% | Medio |
| 10 | AC.03 | `\b(clientes?|deudore(s)?\s*por\s*venta|cuentas?\s*...` | 44 | 14 | 68.2% | Medio |
| 11 | PAT.01 | `\b(capital\s*(pagado|suscrito|social|propio)?|apor...` | 27 | 8 | 70.4% | Medio |
| 12 | AC.05 | `\b(inventario(s)?|existencia(s)?|mercader[ií]a(s)?...` | 7 | 2 | 71.4% | Medio |
| 13 | PC.06 | `\b(remuneracion(es)?|sueldo(s)?|vacaciones?|honora...` | 42 | 11 | 73.8% | Medio |
| 14 | PC.03 | `\bleasing\s*(cp|corriente|corto)?\b...` | 10 | 2 | 80.0% | Medio |
| 15 | AC.07 | `\b(iva\s*(credito|cf)|ppm|impuesto(s)?\s*por\s*rec...` | 14 | 2 | 85.7% | Bajo |
| 16 | AC.01 | `\b(caja\s*chica|caja\s*y\s*banco|efectivo\s*y\s*eq...` | 43 | 6 | 86.0% | Bajo |
| 17 | ANC.03 | `\b(intangible(s)?|goodwill|marca(s)?|patente(s)?|l...` | 8 | 1 | 87.5% | Bajo |
| 18 | ER.02 | `\bcosto(s)?\s*(de\s*)?(venta(s)?|explotacion|produ...` | 9 | 1 | 88.9% | Bajo |
| 19 | PC.05 | `\b(iva\s*(debito|df)|impuesto(s)?\s*por\s*pagar|pr...` | 8 | 0 | 100.0% | Bajo |
| 20 | PC.08 | `\b(anticipo(s)?\s*de\s*cliente(s)?|ingreso(s)?\s*(...` | 5 | 0 | 100.0% | Bajo |
| 21 | PAT.02 | `\b(reserva(s)?(\s*legal)?|prima\s*de\s*emision)\b...` | 7 | 0 | 100.0% | Bajo |
| 22 | ER.04 | `\bgasto(s)?\s*(de\s*)?(administracion|general(es)?...` | 7 | 0 | 100.0% | Bajo |
| 23 | ER.09 | `\bgasto(s)?\s*financiero(s)?|intere(s|ses)?\s*(pag...` | 14 | 0 | 100.0% | Bajo |
| 24 | ER.10 | `\bimpuesto\s*(a\s*la\s*renta|primera\s*categoria)\...` | 6 | 0 | 100.0% | Bajo |
| 25 | ER.11 | `\butilidad\s*neta|resultado\s*neto|net\s*income|ga...` | 2 | 0 | 100.0% | Bajo |

## Detalle por patrón

### #0: AC.01 (confianza=0.9)
**Patrón:** `\b(caja\s*chica|caja\s*y\s*banco|efectivo\s*y\s*equiv|disponible|caja|banco|cuenta\s*corriente\s*banco|cuenta\s*vista)\b`
**Matches:** 43 | **FP:** 6 | **Precisión:** 86.0% | **Riesgo:** Bajo
**Gold standard:** 1/1 correctos (100%)

**Aciertos:**
- Disponible → AC.01
- BANCO CHILE → AC.01
- BANCO SANTANDER → AC.01 (gold)

**Falsos positivos:**
- BANCO SANTANDER US1 (col=perdida) → AC.01: columna 'perdida' incompatible con AC.01 (advertencia)
- Disponible (col=perdida) → AC.01: columna 'perdida' incompatible con AC.01 (advertencia)
- INTERES BANCO 17065433 a 17065433 g (col=perdida) → AC.01: columna 'perdida' incompatible con AC.01 (advertencia)

### #1: AC.02 (confianza=0.92)
**Patrón:** `\b(inversion(es)?\s*(corto\s*plazo|cp)|fondos?\s*mutuos?|dep[oó]sito(s)?\s*a\s*plazo|pacto(s)?)\b`
**Matches:** 5 | **FP:** 2 | **Precisión:** 60.0% | **Riesgo:** Medio

**Aciertos:**
- DEPOSITO A PLAZO EN US$ → AC.02
- Depositos a plazo → AC.02
- Ingresos por Mediciones de Fondos Mutuos → AC.02

**Falsos positivos:**
- Fondo Mutuo CLP (col=activo) → AC.02: new pipeline dice AC.01 (code), regex da AC.02
- Fondo Mutuo CLP (col=activo) → AC.02: new pipeline dice AC.01 (code), regex da AC.02

### #2: AC.03 (confianza=0.9)
**Patrón:** `\b(clientes?|deudore(s)?\s*por\s*venta|cuentas?\s*por\s*cobrar\s*(clientes?)?)\b`
**Matches:** 44 | **FP:** 14 | **Precisión:** 68.2% | **Riesgo:** Medio
**Gold standard:** 2/2 correctos (100%)

**Aciertos:**
- Documentos y cuentas por cobrar empresas relacionadas → AC.03
- GTA. CTE CLIENTES “RO18.047.831 — → AC.03
- o. ANTÍCIFO CLIENTE 245053396 — → AC.03

**Falsos positivos:**
- Documentos y cuentas por cobrar empresas (col=perdida) → AC.03: columna 'perdida' incompatible con AC.03 (advertencia)
- Deudores por venta (neto) (col=perdida) → AC.03: columna 'perdida' incompatible con AC.03 (advertencia)
- Deudores por venta USD (col=perdida) → AC.03: columna 'perdida' incompatible con AC.03 (advertencia)

### #3: AC.04 (confianza=0.92)
**Patrón:** `\b(documento(s)?\s*por\s*cobrar|letras?\s*(por|a)\s*cobrar|pagare(s)?\s*por\s*cobrar|cheques?\s*por\s*cobrar)\b`
**Matches:** 2 | **FP:** 1 | **Precisión:** 50.0% | **Riesgo:** Alto

**Aciertos:**
- Documentos por cobrar (neto) → AC.04

**Falsos positivos:**
- Otros Documentos por Cobrar (col=activo) → AC.04: new pipeline dice AC.01 (code), regex da AC.04

### #4: AC.05 (confianza=0.92)
**Patrón:** `\b(inventario(s)?|existencia(s)?|mercader[ií]a(s)?|stock|materia(s)?\s*prima(s)?|productos?\s*(terminado|en\s*proceso))\b`
**Matches:** 7 | **FP:** 2 | **Precisión:** 71.4% | **Riesgo:** Medio

**Aciertos:**
- MERCADERIAS 1.012.655.946 RETENCION 2? CATEGORIA → AC.05
- MERCADERIAS IMPORTADAS 173.670.519 PROVISION IMPTO, 1? CAT → AC.05
- MERCADERIAS 73.252.176 Total Pasivo Circulante → AC.05

**Falsos positivos:**
- INVENTARIOS (col=desconocido) → AC.05: new pipeline dice AC.01 (code), regex da AC.05
- Otros Inventarios (col=activo) → AC.05: new pipeline dice AC.01 (code), regex da AC.05

### #7: AC.07 (confianza=0.88)
**Patrón:** `\b(iva\s*(credito|cf)|ppm|impuesto(s)?\s*por\s*recuperar|anticipo(s)?\s*(a\s*)?proveedor|gasto(s)?\s*anticipado(s)?|deudore(s)?\s*varios|fondos?\s*por\s*rendir)\b`
**Matches:** 14 | **FP:** 2 | **Precisión:** 85.7% | **Riesgo:** Bajo
**Gold standard:** 2/2 correctos (100%)

**Aciertos:**
- Deudores varios (neto) → AC.07
- PPM → AC.07
- Reajuste PPM-IVA → AC.07

**Falsos positivos:**
- IVA CREDITO FISCAL 693.484.738 676833294 N (col=perdida) → AC.07: columna 'perdida' incompatible con AC.07 (advertencia)
- Deudores Varios (col=activo) → AC.07: new pipeline dice AC.01 (code), regex da AC.07

### #8: ANC.01 (confianza=0.9)
**Patrón:** `\b(activo\s*fijo|propiedad(es)?\s*planta|maquinaria(s)?|veh[ií]culo(s)?|terreno(s)?|construccion(es)?|mueble(s)?\s*y\s*[uú]til(es)?|equipos?\s*(de\s*)?computacion)\b`
**Matches:** 46 | **FP:** 16 | **Precisión:** 65.2% | **Riesgo:** Medio
**Gold standard:** 5/8 correctos (62%)

**Aciertos:**
- Construcciones y obras de infraestructura → ANC.01
- CONSTRUCCIONES → ANC.01
- o VEHICULOS → ANC.01

**Falsos positivos:**
- MAQUINARIA 211376247 43.379.018 227.497:225 (col=perdida) → ANC.01: columna 'perdida' incompatible con ANC.01 (advertencia)
- : MAQUINARIA 579.394.650 1.698.296 — (col=perdida) → ANC.01: columna 'perdida' incompatible con ANC.01 (advertencia)
- : VEHICULOS (col=ganancia) → ANC.01: gold standard dice ANC.03 (regex da ANC.01)

### #9: ANC.03 (confianza=0.9)
**Patrón:** `\b(intangible(s)?|goodwill|marca(s)?|patente(s)?|licencia(s)?|software|llave\s*de\s*negocio)\b`
**Matches:** 8 | **FP:** 1 | **Precisión:** 87.5% | **Riesgo:** Bajo

**Aciertos:**
- o LICENCIAS → ANC.03
- l PATENTES → ANC.03
- SOFTWARE → ANC.03

**Falsos positivos:**
- PATENTES “2301974 (col=perdida) → ANC.03: columna 'perdida' incompatible con ANC.03 (advertencia)

### #12: PC.01 (confianza=0.9)
**Patrón:** `\b(proveedor(es)?|acreedore(s)?\s*comercial|facturas?\s*por\s*pagar|cuentas?\s*por\s*pagar\s*proveedor)\b`
**Matches:** 9 | **FP:** 3 | **Precisión:** 66.7% | **Riesgo:** Medio
**Gold standard:** 2/4 correctos (50%)

**Aciertos:**
- e ANTICIPO PROVEEDORES 1.348.569.258 —1077.117.567 → PC.01
- : PROVEEDORES 3776402807 — → PC.01
- 2301-03 PROVEEDORES 5.295.438.712] 5.928.781.12% S → PC.01

**Falsos positivos:**
- ANTICIPO PROVEEDORES (col=ganancia) → PC.01: new pipeline dice AC.01 (learning_fuzzy), regex da PC.01
- Anticipo a Proveedores (col=activo) → PC.01: gold standard dice AC.01 (regex da PC.01)
- Anticipo a Proveedores (col=activo) → PC.01: gold standard dice AC.01 (regex da PC.01)

### #14: PC.03 (confianza=0.9)
**Patrón:** `\bleasing\s*(cp|corriente|corto)?\b`
**Matches:** 10 | **FP:** 2 | **Precisión:** 80.0% | **Riesgo:** Medio

**Aciertos:**
- Arriendo por Leasing → PC.03
- Arriendos por Leasing → PC.03
- TAX ASSETS, CURRENT 16.603 11.373 LEASING PAYABLES → PC.03

**Falsos positivos:**
- Depreciación Acum. Activos en Leasing (col=pasivo) → PC.03: new pipeline dice AC.01 (code), regex da PC.03
- Impto. Dif. por Oblig Leasing (col=activo) → PC.03: new pipeline dice AC.07 (code), regex da PC.03

### #16: PC.05 (confianza=0.88)
**Patrón:** `\b(iva\s*(debito|df)|impuesto(s)?\s*por\s*pagar|provision\s*impuesto|impuesto\s*(a\s*la\s*)?renta|primera\s*categoria|impuesto\s*unico|ppm\s*por\s*pagar|impt?o\s*por\s*pagar)\b`
**Matches:** 8 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo
**Gold standard:** 4/4 correctos (100%)

**Aciertos:**
- o IVA DEBITO FISCAL 1094475.077 — → PC.05
- TARJETA DE CREDITO 756.630 IVA DEBITO FISCAL, → PC.05
- : ANTICIPO REMUNERACIONES 544,288 IVA DEBITO FISCAL → PC.05

### #17: PC.06 (confianza=0.86)
**Patrón:** `\b(remuneracion(es)?|sueldo(s)?|vacaciones?|honorario(s)?\s*por\s*pagar|gratificacion(es)?|imposicion(es)?|afp|isapre|leyes\s*sociales|finiquito(s)?|indemnizacion)\b`
**Matches:** 42 | **FP:** 11 | **Precisión:** 73.8% | **Riesgo:** Medio
**Gold standard:** 5/12 correctos (42%)

**Aciertos:**
- AFP → PC.06
- E GRATIFICACION → PC.06
- INDEMNIZACION → PC.06

**Falsos positivos:**
- 0 REMUNERACIONES (col=pasivo) → PC.06: new pipeline dice ER.04 (learning_fuzzy), regex da PC.06
- > Remuneraciones (col=ganancia) → PC.06: gold standard dice ER.04 (regex da PC.06)
- Remuneraciones (col=ganancia) → PC.06: gold standard dice ER.04 (regex da PC.06)

### #19: PC.08 (confianza=0.85)
**Patrón:** `\b(anticipo(s)?\s*de\s*cliente(s)?|ingreso(s)?\s*(percibido|recibido).*(adelantado|anticipado)|otros?\s*pasivos?\s*(corrientes?|circulantes?)|provision(es)?\s*varia(s)?|acreedore(s)?\s*vario(s)?)\b`
**Matches:** 5 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo
**Gold standard:** 1/1 correctos (100%)

**Aciertos:**
- o. ACREEDORES VARIOS → PC.08
- : PROVISIONES VARIAS → PC.08 (gold)
- SCOTIABANK 223.810 ACREEDORES VARIOS → PC.08

### #22: PNC.03 (confianza=0.9)
**Patrón:** `\b(bono(s)?|debenture(s)?)\b`
**Matches:** 3 | **FP:** 1 | **Precisión:** 66.7% | **Riesgo:** Medio

**Aciertos:**
- BONOS → PNC.03
- BONOS + → PNC.03

**Falsos positivos:**
- Bono (col=ganancia) → PNC.03: columna 'ganancia' incompatible con PNC.03 (advertencia)

### #25: PAT.01 (confianza=0.9)
**Patrón:** `\b(capital\s*(pagado|suscrito|social|propio)?|aporte(s)?\s*(de\s*)?(capital|socios?))\b`
**Matches:** 27 | **FP:** 8 | **Precisión:** 70.4% | **Riesgo:** Medio
**Gold standard:** 7/7 correctos (100%)

**Aciertos:**
- Capital pagado → PAT.01 (gold)
- Reserva revalorización capital → PAT.01
- CAPITAL SOCIAL → PAT.01 (gold)

**Falsos positivos:**
- VESSELS AND MACHINERIES 31.634.183 35.015.073 PAID CAPITAL (col=perdida) → PAT.01: columna 'perdida' incompatible con PAT.01 (advertencia)
- Reservas revalorización capital (col=perdida) → PAT.01: columna 'perdida' incompatible con PAT.01 (advertencia)
- CAPITAL EMITIDO (col=desconocido) → PAT.01: new pipeline dice PC.01 (code), regex da PAT.01

### #26: PAT.02 (confianza=0.88)
**Patrón:** `\b(reserva(s)?(\s*legal)?|prima\s*de\s*emision)\b`
**Matches:** 7 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo
**Gold standard:** 5/5 correctos (100%)

**Aciertos:**
- RESERVA FUTUROS DIVIDENDOS → PAT.02
- Piscicultura 113.293.296 Otras Reservas → PAT.02
- OTRAS RESERVAS → PAT.02 (gold)

### #27: PAT.03 (confianza=0.9)
**Patrón:** `\b(utilidad(es)?\s*(acumulada(s)?|retenida(s)?)|resultado(s)?\s*acumulado(s)?|p[eé]rdida(s)?\s*acumulada(s)?)\b`
**Matches:** 11 | **FP:** 4 | **Precisión:** 63.6% | **Riesgo:** Medio
**Gold standard:** 4/4 correctos (100%)

**Aciertos:**
- Utilidades acumuladas → PAT.03 (gold)
- UTILIDADES ACUMULADAS → PAT.03 (gold)
- PERDIDAS ACUMULADAS → PAT.03 (gold)

**Falsos positivos:**
- GANANCIA (PERDIDA) ACUMULADA (col=desconocido) → PAT.03: new pipeline dice PC.01 (code), regex da PAT.03
- Utilidades (Perdidas) Acumuladas (col=pasivo) → PAT.03: new pipeline dice PC.01 (code), regex da PAT.03
- GANANCIA (PERDIDA) ACUMULADA (col=desconocido) → PAT.03: new pipeline dice PC.01 (code), regex da PAT.03

### #28: PAT.04 (confianza=0.92)
**Patrón:** `\butilidad\s*del\s*(ejercicio|periodo|a[ñn]o)|resultado\s*del\s*(ejercicio|periodo)|p[eé]rdida\s*del\s*(ejercicio|periodo)|utilidad\s*[/(]?\s*p[eé]rdida\b`
**Matches:** 21 | **FP:** 8 | **Precisión:** 61.9% | **Riesgo:** Medio

**Aciertos:**
- : MN UTILIDAD DEL EJERCICIO → PAT.04
- INSTALACIONES 39.578.745 UTILIDAD DEL EJERCICIO → PAT.04
- UTILIDAD DEL EJERCICIO → PAT.04

**Falsos positivos:**
- Utilidad (pérdida) del ejercicio (col=perdida) → PAT.04: columna 'perdida' incompatible con PAT.04 (advertencia)
- UTILIDAD DEL EJERCICIO (col=perdida) → PAT.04: columna 'perdida' incompatible con PAT.04 (advertencia)
- UTILIDAD DEL EJERCICIO (col=perdida) → PAT.04: columna 'perdida' incompatible con PAT.04 (advertencia)

### #29: ER.01 (confianza=0.9)
**Patrón:** `\b(venta(s)?|ingreso(s)?\s*(por\s*venta|operacional|del\s*giro)|facturacion)\b`
**Matches:** 18 | **FP:** 6 | **Precisión:** 66.7% | **Riesgo:** Medio
**Gold standard:** 0/4 correctos (0%)

**Aciertos:**
- OTRAS VENTAS → ER.01
- Otras Ventas Fuera del Giro → ER.01
- GASTOS DE ADMINISTRACIÓN Y VENTA → ER.01

**Falsos positivos:**
- ¡ Ventas (col=ganancia) → ER.01: gold standard dice PAT.01 (regex da ER.01)
- Ventas (col=ganancia) → ER.01: gold standard dice PAT.01 (regex da ER.01)
- Comisiones por Ventas (col=ganancia) → ER.01: new pipeline dice ER.05 (dictionary_exact), regex da ER.01

### #30: ER.02 (confianza=0.92)
**Patrón:** `\bcosto(s)?\s*(de\s*)?(venta(s)?|explotacion|produccion|mercader[ií]a)\b`
**Matches:** 9 | **FP:** 1 | **Precisión:** 88.9% | **Riesgo:** Bajo

**Aciertos:**
- 0 COSTO VENTA ACTIVO → ER.02
- COSTO VENTA → ER.02
- Costo de Ventas → ER.02

**Falsos positivos:**
- COSTO VENTA FRUTA (col=activo) → ER.02: columna 'activo' incompatible con ER.02 (advertencia)

### #31: ER.04 (confianza=0.88)
**Patrón:** `\bgasto(s)?\s*(de\s*)?(administracion|general(es)?|gestion)\b`
**Matches:** 7 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo
**Gold standard:** 2/2 correctos (100%)

**Aciertos:**
- Recuperacion Gastos de Administracion → ER.04
- Gastos Generales → ER.04 (gold)
- GASTOS GENERALES 19315181 8 19315181 B g a → ER.04

### #33: ER.07 (confianza=0.9)
**Patrón:** `\b(depreciacion|amortizacion)\b`
**Matches:** 7 | **FP:** 3 | **Precisión:** 57.1% | **Riesgo:** Alto
**Gold standard:** 4/4 correctos (100%)

**Aciertos:**
- DEPRECIACION → ER.07 (gold)
- DEPRECIACION → ER.07 (gold)
- Depreciacion → ER.07 (gold)

**Falsos positivos:**
- DEPRECIACION ACUMULADA (col=ganancia) → ER.07: new pipeline dice ANC.01 (dictionary_exact), regex da ER.07
- DEPRECIACION ACUMULADA (col=ganancia) → ER.07: new pipeline dice ANC.01 (dictionary_exact), regex da ER.07
- DEPRECIACION ACUMULADA (col=ganancia) → ER.07: new pipeline dice ANC.01 (dictionary_exact), regex da ER.07

### #34: ER.09 (confianza=0.9)
**Patrón:** `\bgasto(s)?\s*financiero(s)?|intere(s|ses)?\s*(pagado|bancario|leasing|factoring)|comision(es)?\s*bancaria(s)?`
**Matches:** 14 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo
**Gold standard:** 8/8 correctos (100%)

**Aciertos:**
- INTERESES BANCARIOS → ER.09 (gold)
- i GASTOS FINANCIEROS → ER.09
- Intereses Pagados o Adeudados → ER.09

### #35: ER.10 (confianza=0.9)
**Patrón:** `\bimpuesto\s*(a\s*la\s*renta|primera\s*categoria)\b`
**Matches:** 6 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo

**Aciertos:**
- pe Impuesto a la Renta y → ER.10
- Impuesto a la Renta → ER.10
- Impuesto a la Renta → ER.10

### #36: ER.11 (confianza=0.92)
**Patrón:** `\butilidad\s*neta|resultado\s*neto|net\s*income|ganancia\s*neta`
**Matches:** 2 | **FP:** 0 | **Precisión:** 100.0% | **Riesgo:** Bajo

**Aciertos:**
- NET INCOME FOR THE PERIOD → ER.11
- Ganancia neta → ER.11

## Recomendaciones

### Migrar sin cambios (7 patrones)
- `\bgasto(s)?\s*financiero(s)?|intere(s|ses)?\s*(pagado|bancar...` → ER.09 (precisión 100.0%, 14 matches)
- `\b(iva\s*(debito|df)|impuesto(s)?\s*por\s*pagar|provision\s*...` → PC.05 (precisión 100.0%, 8 matches)
- `\b(reserva(s)?(\s*legal)?|prima\s*de\s*emision)\b...` → PAT.02 (precisión 100.0%, 7 matches)
- `\bgasto(s)?\s*(de\s*)?(administracion|general(es)?|gestion)\...` → ER.04 (precisión 100.0%, 7 matches)
- `\bimpuesto\s*(a\s*la\s*renta|primera\s*categoria)\b...` → ER.10 (precisión 100.0%, 6 matches)
- `\b(anticipo(s)?\s*de\s*cliente(s)?|ingreso(s)?\s*(percibido|...` → PC.08 (precisión 100.0%, 5 matches)
- `\butilidad\s*neta|resultado\s*neto|net\s*income|ganancia\s*n...` → ER.11 (precisión 100.0%, 2 matches)

### Necesitan ajustes (8 patrones)
- `\b(caja\s*chica|caja\s*y\s*banco|efectivo\s*y\s*equiv|dispon...` → AC.01 (precisión 86.0%, 6 FP)
  - FP: BANCO SANTANDER US1 → columna 'perdida' incompatible con AC.01 (advertencia)
  - FP: Disponible → columna 'perdida' incompatible con AC.01 (advertencia)
- `\b(remuneracion(es)?|sueldo(s)?|vacaciones?|honorario(s)?\s*...` → PC.06 (precisión 73.8%, 11 FP)
  - FP: 0 REMUNERACIONES → new pipeline dice ER.04 (learning_fuzzy), regex da PC.06
  - FP: > Remuneraciones → gold standard dice ER.04 (regex da PC.06)
- `\b(capital\s*(pagado|suscrito|social|propio)?|aporte(s)?\s*(...` → PAT.01 (precisión 70.4%, 8 FP)
  - FP: VESSELS AND MACHINERIES 31.634.183 35.015.073 PAID CAPITAL → columna 'perdida' incompatible con PAT.01 (advertencia)
  - FP: Reservas revalorización capital → columna 'perdida' incompatible con PAT.01 (advertencia)
- `\b(iva\s*(credito|cf)|ppm|impuesto(s)?\s*por\s*recuperar|ant...` → AC.07 (precisión 85.7%, 2 FP)
  - FP: IVA CREDITO FISCAL 693.484.738 676833294 N → columna 'perdida' incompatible con AC.07 (advertencia)
  - FP: Deudores Varios → new pipeline dice AC.01 (code), regex da AC.07
- `\bleasing\s*(cp|corriente|corto)?\b...` → PC.03 (precisión 80.0%, 2 FP)
  - FP: Depreciación Acum. Activos en Leasing → new pipeline dice AC.01 (code), regex da PC.03
  - FP: Impto. Dif. por Oblig Leasing → new pipeline dice AC.07 (code), regex da PC.03
- `\bcosto(s)?\s*(de\s*)?(venta(s)?|explotacion|produccion|merc...` → ER.02 (precisión 88.9%, 1 FP)
  - FP: COSTO VENTA FRUTA → columna 'activo' incompatible con ER.02 (advertencia)
- `\b(intangible(s)?|goodwill|marca(s)?|patente(s)?|licencia(s)...` → ANC.03 (precisión 87.5%, 1 FP)
  - FP: PATENTES “2301974 → columna 'perdida' incompatible con ANC.03 (advertencia)
- `\b(inventario(s)?|existencia(s)?|mercader[ií]a(s)?|stock|mat...` → AC.05 (precisión 71.4%, 2 FP)
  - FP: INVENTARIOS → new pipeline dice AC.01 (code), regex da AC.05
  - FP: Otros Inventarios → new pipeline dice AC.01 (code), regex da AC.05

### Eliminar o rediseñar (10 patrones)
- `\b(activo\s*fijo|propiedad(es)?\s*planta|maquinaria(s)?|veh[...` → ANC.01 (precisión 65.2%, 16 FP)
- `\b(clientes?|deudore(s)?\s*por\s*venta|cuentas?\s*por\s*cobr...` → AC.03 (precisión 68.2%, 14 FP)
- `\butilidad\s*del\s*(ejercicio|periodo|a[ñn]o)|resultado\s*de...` → PAT.04 (precisión 61.9%, 8 FP)
- `\b(venta(s)?|ingreso(s)?\s*(por\s*venta|operacional|del\s*gi...` → ER.01 (precisión 66.7%, 6 FP)
- `\b(utilidad(es)?\s*(acumulada(s)?|retenida(s)?)|resultado(s)...` → PAT.03 (precisión 63.6%, 4 FP)
- `\b(proveedor(es)?|acreedore(s)?\s*comercial|facturas?\s*por\...` → PC.01 (precisión 66.7%, 3 FP)
- `\b(depreciacion|amortizacion)\b...` → ER.07 (precisión 57.1%, 3 FP)
- `\b(inversion(es)?\s*(corto\s*plazo|cp)|fondos?\s*mutuos?|dep...` → AC.02 (precisión 60.0%, 2 FP)
- `\b(bono(s)?|debenture(s)?)\b...` → PNC.03 (precisión 66.7%, 1 FP)
- `\b(documento(s)?\s*por\s*cobrar|letras?\s*(por|a)\s*cobrar|p...` → AC.04 (precisión 50.0%, 1 FP)

### Sin datos disponibles (12 patrones)
- `\b(relacionada(s)?\s*(cp|corriente)|cuenta\s*corriente\s*rel...` → AC.06 (0 matches en la muestra)
- `(cuenta\s+(particular|corriente)\s+(socio|accionista))|(cta\...` → AC.06S (0 matches en la muestra)
- `\b(inversion(es)?\s*(permanente(s)?|lp|largo\s*plazo)|accion...` → ANC.04 (0 matches en la muestra)
- `\b(relacionada(s)?\s*(lp|largo\s*plazo))\b...` → ANC.05 (0 matches en la muestra)
- `\b(obligaciones?\s*bancarias?\s*(cp|corto)?|credito(s)?\s*ba...` → PC.02 (0 matches en la muestra)
- `\bfactoring\b...` → PC.04 (0 matches en la muestra)
- `\b(relacionada(s)?\s*(cp|corriente)\s*pasivo|cta\s*cte\s*soc...` → PC.07 (0 matches en la muestra)
- `\b(obligaciones?\s*bancarias?\s*(lp|largo)|credito(s)?\s*ban...` → PNC.01 (0 matches en la muestra)
- `\bleasing\s*(lp|largo)\b...` → PNC.02 (0 matches en la muestra)
- `\b(relacionada(s)?\s*(lp|largo)\s*pasivo)\b...` → PNC.04 (0 matches en la muestra)
- `\b(indemnizacion(es)?\s*(por\s*)?a[ñn]os?\s*(de\s*)?servicio...` → PNC.05 (0 matches en la muestra)
- `\bgasto(s)?\s*(de\s*)?(venta(s)?|comercial(es)?|marketing|di...` → ER.05 (0 matches en la muestra)

## Top 10 regex con mejor ROI

| # | Código | Matches | FP | Precisión | Recuperación |
|---|--------|---------|----|-----------|-------------|
| 1 | AC.01 | 43 | 6 | 86.0% | 43 cuentas |
| 2 | PC.06 | 42 | 11 | 73.8% | 42 cuentas |
| 3 | PAT.01 | 27 | 8 | 70.4% | 27 cuentas |
| 4 | AC.07 | 14 | 2 | 85.7% | 14 cuentas |
| 5 | ER.09 | 14 | 0 | 100.0% | 14 cuentas |
| 6 | PC.03 | 10 | 2 | 80.0% | 10 cuentas |
| 7 | ER.02 | 9 | 1 | 88.9% | 9 cuentas |
| 8 | ANC.03 | 8 | 1 | 87.5% | 8 cuentas |
| 9 | PC.05 | 8 | 0 | 100.0% | 8 cuentas |
| 10 | AC.05 | 7 | 2 | 71.4% | 7 cuentas |

**Total recuperado con top 10:** 182 cuentas

## Cobertura esperada después de implementación

Escenario: implementar las Top 10 regex + las que precisión ≥ 90%
- Patrones a implementar: 15
- Cuentas recuperables: 209
- Reducción de 'sin clasificar': 209 cuentas
