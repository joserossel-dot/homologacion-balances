# Informe de Inteligencia del Sistema

**Generado:** 2026-07-06
**Fuentes:** Gold Standard (187 registros), Validación (88 empresas, 5.369 cuentas), 4.100 cuentas sin clasificar

---

## 1. Top 500 Cuentas Sin Clasificar

Archivo completo en `reports/validation/20260706_200251/unclassified.xlsx` (4.100 filas).

### Partición real vs ruido

| Tipo | Ocurrencias | Nombres únicos |
|------|-------------|-----------------|
| Cuentas reales | **3.525** (86%) | 2.087 |
| Ruido (encabezados, fechas, RUT, páginas) | **575** (14%) | 460 |

De las cuentas reales:
- **1.652** tienen código contable (47%)
- **1.873** NO tienen código (53%)

### Top 20 reales con código (más frecuentes entre empresas)

| # | Cuenta | Frecuencia | Código(s) |
|---|--------|-----------|-----------|
| 1 | Caja | 7 | 1.1.01.001, 1.1.10.111, 1-1-01-01 |
| 2 | Fertilizantes | 6 | 1-1-08-16, 3.1.20.123, 3-2-01-06 |
| 3 | Vehiculos | 6 | 1.2.20.005, 1-2-04-01 |
| 4 | Banco BCI | 5 | 1.1.10.115, 1101203, 1.1.02.002 |
| 5 | Deudores Varios | 5 | 1.1.06.001, 1-1-04-6-02 |
| 6 | CUENTAS POR PAGAR | 4 | 2-1-05-101, 2-1-03-004, 2102001000 |
| 7 | Casa Inquilino | 4 | 1.2.20.009, 1.1.03.007 |
| 8 | Prestamos Trabajadores | 4 | 1.1.04.002 |
| 9 | Cuentas Varias Por Cobrar | 4 | 1.1.05.001 |
| 10 | Iva Credito no Incluido | 4 | 1.1.08.007 |
| 11 | Depreciacion Acumulada | 4 | 1.2.20.020 |
| 12 | Cuentas Por Pagar Oficina | 4 | 2.1.01.002 |
| 13 | Asesorias AGI Ltda | 4 | 2.1.01.004 |
| 14 | Pagare Ases. San Roque | 4 | 2.1.01.006 |
| 15 | Pagare Exportadora Baika | 4 | 2.1.01.007 |
| 16 | Ptmo. BCI | 4 | 2.1.04.003 |
| 17 | Impto. Unico Segunda Categoria | 4 | 2.1.07.004 |
| 18 | Utilidades Retenidas | 4 | 2.3.10.003 |
| 19 | Suministros | 4 | 3.1.05.002 |
| 20 | Comb. Lubricantes Y Otros | 4 | 3.1.05.010 |

### Top 20 reales SIN código (requieren fuzzy matching)

| # | Cuenta | Frecuencia |
|---|--------|-----------|
| 1 | CAJA | 13 |
| 2 | BANCO CORPBANCA | 11 |
| 3 | DEPRECIACION ACUMULADA | 10 |
| 4 | REMUNERACIONES POR | 9 |
| 5 | CUENTAS POR PAGAR | 8 |
| 6 | VACACIONES PROPORCIONALES | 5 |
| 7 | COMISIONES | 5 |
| 8 | SEGURO CESANTIA | 5 |
| 9 | VEHICULOS | 4 |
| 10 | LINEA CREDITO SECURITY | 4 |
| 11 | PPM | 4 |
| 12 | IMPUESTO UNICO | 4 |
| 13 | IVA D.F | 4 |
| 14 | REVALORACION CAPITAL | 4 |
| 15 | ARRIENDO MAQUINARIA | 4 |
| 16 | BIENES RAICES | 4 |
| 17 | UTILIDAD POR DISTRIBUIR | 4 |
| 18 | HORAS EXTRAS | 4 |
| 19 | INTERESES L/CREDITO | 4 |
| 20 | RESULTADOS EJERCICIOS | 4 |

---

## 2. Agrupación de Nombres Equivalentes

### Variantes por normalización semántica (75+ grupos detectados)

#### Grupo: CAJA (24 ocurrencias, 2 variantes)
- CAJA → Caja
- → Solución: Normalizar a mayúsculas en GS, una sola entrada `CAJA` → `AC.01`

#### Grupo: CUENTAS POR PAGAR (16 ocurrencias, 3 variantes)
- CUENTAS POR PAGAR, Cuentas por pagar, (coma prefijo)
- → Solución: GS ya contiene `Cuentas por Pagar` (PC.07). Agregar alias.

#### Grupo: DEPRECIACION ACUMULADA (15 ocurrencias, 2 variantes)
- DEPRECIACION ACUMULADA, Depreciacion Acumulada
- → GS no contiene "Depreciacion Acumulada" como tal. Hay `Depreciaciones` (ER.07) y `Depr. Acum. Instalaciones`. Falta entrada genérica.

#### Grupo: VEHICULOS (12 ocurrencias, 2 variantes)
- VEHICULOS, Vehiculos
- → GS no tiene "Vehículos". Hay `Vehiculos` (ANC.03) con 1 uso.

#### Grupo: BANCO CORPBANCA (12 ocurrencias, 2 variantes)
- BANCO CORPBANCA, BANCO CORPBANCA (DOLARES)
- → No está en GS. Misma lógica que otros bancos (Santander, BCI, etc).

#### Grupo: BANCO SECURITY (10 ocurrencias, 3 variantes)
- BANCO SECURITY, Banco Security, Banco Security USD
- → No está en GS.

#### Grupo: DEUDORES VARIOS (8 ocurrencias, 2 variantes)
- DEUDORES VARIOS, Deudores Varios
- → GS no tiene. Misma familia que `Varios Acreedores`, `Acreedores Varios`.

#### Grupo: FONDOS MUTUOS (8 ocurrencias, 3 variantes)
- FONDOS MUTUOS, Fondos Mutuos, Fondos Mutuos Pesos
- → No está en GS.

#### Grupo: OTROS GASTOS DEL PERSONAL (7 ocurrencias, 2 variantes)
- → No está en GS. Familia: Gastos de Oficina, Gastos Generales (sí en GS).

#### Grupos adicionales (top por tamaño):
- **IMPUESTO UNICO**: 6 ocurrencias → GS tiene `Impuesto Único Trabajadores` (PC.05)
- **GASTOS DE OFICINA**: 5 ocurrencias → GS tiene `Gastos de Oficina (O)` (ER.04)
- **TRANSPORTE DE PERSONAL**: 6 ocurrencias → No está en GS
- **FLETES**: 6 ocurrencias → No está en GS
- **COMBUSTIBLES**: 6 ocurrencias → No está en GS
- **ENERGIA ELECTRICA**: 5 ocurrencias → No está en GS
- **GASTOS COMPUTACIONALES**: 5 ocurrencias → No está en GS

---

## 3. Familias Repetidas Detectadas

### Familia: Instalaciones / Equipos / Maquinarias (ANC.01)
- Instalaciones — GS: sí (ANC.01, 9 usos)
- Equipos — GS: NO
- Equipos Computacionales — GS: sí (ANC.01, 3 usos)
- Maquinarias — GS: NO
- Maquinarias y Equipos — GS: sí (ANC.01, 1 uso)
- Muebles Y Utiles — GS: sí (ANC.01, 4 usos)
- Equipos de Riego — GS: NO
- Equipo Telefónico — GS: NO
- Equipos de Radio — GS: NO

### Familia: Depreciaciones (ANC.01 / ER.07)
- Depreciacion Acumulada — GS: NO (solo `Depreciaciones` ER.07)
- Depr. Acum. Instalaciones — GS: NO
- Depr. Acum Equipos — GS: NO
- Deprec. Instalaciones (O) — GS: NO
- Depreciacion Pozo Profundo — GS: NO
- Dep. Acum. Vehiculos — GS: NO
- Dep. Acum. + decenas de activos agrícolas — GS: NO

### Familia: Bancos (AC.01)
- Banco Santander — GS: sí (6 usos)
- BANCO BCI — GS: NO (solo `Banco BCI USD`)
- Banco Chile — GS: NO
- Banco BBVA — GS: sí (1 uso)
- Banco Security — GS: NO
- Banco Corpbanca — GS: NO
- Banco Estado — GS: NO
- Banco Itau — GS: NO

### Familia: Prestamos / Préstamos (PC.02 / PNC.01)
- Prestamo Bancario Corto Plazo — GS: sí (1 uso)
- Prestamo Bancario Largo Plazo — GS: sí (1 uso)
- Ptmo. BCI — GS: NO
- Ptmo Santander — GS: NO (múltiples variantes)
- Prestamos Trabajadores — GS: NO
- Prestamos al Personal — GS: NO
- Prestamos a Terceros — GS: NO
- Préstamos L/Plazo M.Extranjera — GS: NO

### Familia: Agrícola (múltiples cuentas)
- Fertilizantes, Herbicidas, Foliares, Combustibles y Lubricantes
- Plantaciones de Cerezos, Avellanos, Manzanos, Arandanos
- Parronales, Viveros, Invernaderos
- Equipos de Riego, Pozo Profundo, Plantas de Osmosis
- Dep. Acum. de todos los anteriores
- **Ninguna de estas cuentas existe en GS.** Esto se debe a que la validación se hizo con 88 empresas del sector agrícola.

### Familia: Sueldos / Remuneraciones (PC.06 / ER.04)
- Remuneraciones — GS: sí (5 usos)
- Sueldos Por Pagar — GS: sí (4 usos)
- Honorarios — GS: sí (4 usos)
- Vacaciones Proporcionales — GS: NO
- Horas Extras — GS: NO
- Indemnizaciones — GS: NO
- Colacion, Movilizacion — GS: NO

### Familia: IVA / Impuestos (PC.05 / AC.07)
- Iva Credito Fiscal — GS: sí (5 usos)
- Iva Debito Fiscal — GS: sí (6 usos)
- Iva Credito no Incluido — GS: NO
- IVA D.F — GS: NO
- PPM — GS: NO (hay P.P.M. Por Pagar, P.P.M. del Ejercicio)
- Impuesto Unico — GS: NO (hay `Impuesto Único Trabajadores`)
- Impuesto Diferido — GS: sí
- Impuesto Renta — GS: sí

---

## 4. Cuentas que Aparecen en Muchas Empresas

(Medido por frecuencia del mismo código a través de empresas diferentes)

| Código | Empresas | Cuenta típica |
|--------|----------|---------------|
| 1.1.01.001 | 4 | Caja |
| 1.1.04.002 | 4 | Prestamos Trabajadores |
| 1.1.05.001 | 4 | Cuentas Varias Por Cobrar |
| 1.1.06.001 | 4 | Deudores Varios |
| 1.2.20.005 | 4 | Vehiculos |
| 1.2.20.020 | 4 | Depreciacion Acumulada |
| 2.1.01.002 | 4 | Cuentas Por Pagar Oficina |
| 2.1.04.003 | 4 | Ptmo. BCI |
| 211001 | 4 | Documentos por Pagar E.E.R.R |
| 2.3.10.003 | 4 | Utilidades Retenidas |
| 3.1.05.002 | 4 | Suministros |
| 3.1.05.016 | 4 | Asesorias |

Hay **633 códigos distintos** que aparecen en 2+ empresas. Cada uno representa una cuenta que se repite trans-empresa, ideal para aprendizaje por lote.

---

## 5. Cuentas Auto-Aprendibles Automáticamente

### Estrategias de autoaprendizaje (sin reglas manuales)

#### A. Coincidencia exacta con GS (case-insensitive): **43 ocurrencias**, 14 nombres únicos
Ejemplos: `Caja` → GS: `CAJA`, `Fondos por Rendir` → GS: `Fondos por Rendir`
- **Impacto inmediato**: agregar estos 14 nombres al GS si no existen, o mejorar el matcher para que ignore mayúsculas/minúsculas.

#### B. Coincidencia de código: **0 ocurrencias**
Ninguna cuenta sin clasificar tiene un código que ya exista en GS con el mismo nombre.

#### C. Coincidencia parcial de nombre: **612 ocurrencias**
Ejemplos: `Gastos de Oficina` → GS: `Gastos de Oficina (O)`, `Depreciacion Acumulada` → GS: `Depreciaciones`
- **Impacto alto**: El Learning Engine ya captura algunas, pero no las que son substring/superstring del GS.

#### D. Fuzzy match > 85%: **40 ocurrencias adicionales**
Nombres como `CAJA` que son similares a `Caja` en GS pero con suficiente diferencia para no matchear.

#### E. Aprendizaje por lote (códigos repetidos): **633 códigos**
Cuentas como `1.1.01.001 → Caja` aparecen en 4 empresas. Aprendiendo una, se clasifican las otras automáticamente.

---

## 6. Estimación de Cobertura Adicional

| Estrategia | Ganancia estimada |
|------------|-------------------|
| A. Coincidencia exacta (case-insensitive) | +43 |
| C. Coincidencia parcial de nombre | +612 |
| D. Fuzzy match > 85% | +40 |
| E. Aprendizaje por lote (50% de códigos repetidos) | +316 |
| **Total estimado** | **+1.011** |

### Proyección

| Métrica | Actual | Con mejoras | Potencial máximo |
|---------|--------|-------------|------------------|
| Cuentas clasificadas | 1.269 | **2.280** | 4.794 |
| Cobertura | 23,6% | **42,5%** | 89,3% |
| Sin clasificar | 4.100 | 3.089 | 575 (solo ruido) |

El **techo máximo** es ~89.3% (clasificar todas las cuentas reales), dejando solo 575 filas de ruido (encabezados, RUTs, páginas).

---

## 7. Las 20 Mejoras con Mayor Impacto

Priorizadas por: impacto en cobertura × facilidad de implementación × frecuencia de la cuenta.

### Inmediatas (solo datos, sin código nuevo)

| # | Mejora | Ganancia | Esfuerzo |
|---|--------|----------|----------|
| 1 | **Agregar "CAJA" mayúscula como alias en GS** | +13 ya, potencial +16 total | 1 línea |
| 2 | **Agregar "DEPRECIACION ACUMULADA" genérica (ANC)** | +11 ya, +15 total | 1 línea |
| 3 | **Agregar "CUENTAS POR PAGAR" genérica (PC.07)** | +12 ya, +16 total | 1 línea |
| 4 | **Agregar "BANCO CORPBANCA" + "(DOLARES)" (AC.01)** | +11 | 2 líneas |
| 5 | **Agregar "BANCO SECURITY" + "USD" (AC.01)** | +10 | 2 líneas |
| 6 | **Agregar "VEHICULOS" mayúscula como alias (ANC.03)** | +6 ya, +12 total | 1 línea |
| 7 | **Agregar "FONDOS MUTUOS" y variantes (AC.01)** | +6 | 2 líneas |
| 8 | **Agregar "DEUDORES VARIOS" / "VARIOS DEUDORES" (PC.08)** | +8 | 1 línea |
| 9 | **Agregar "REMUNERACIONES POR" como alias** | +9 | 1 línea |
| 10 | **Agregar "MANTENCION" (ER.04, similar a Gastos Generales)** | +7 | 1 línea |

### De infraestructura (mejorar matchers)

| # | Mejora | Ganancia | Esfuerzo |
|---|--------|----------|----------|
| 11 | **Matcher case-insensitive** en Learning Engine | +43 (incluye #1, #3, #6) | Bajo |
| 12 | **Matcher por substring** (e.g. "Gastos de Oficina" → "Gastos de Oficina (O)") | +612 | Medio |
| 13 | **Auto-aprender códigos repetidos**: cuando 2+ empresas usan mismo código→misma cuenta, aprender automáticamente | +316 | Medio |
| 14 | **Fuzzy matcher > 0.85** en Learning Engine | +40 | Bajo |

### De diccionario (agregar familias completas)

| # | Mejora | Ganancia | Esfuerzo |
|---|--------|----------|----------|
| 15 | **Agregar familia agrícola**: Fertilizantes, Herbicidas, Foliares, Combustibles Agrícolas, etc. | ~30+ | Medio |
| 16 | **Agregar familia Depreciación Acumulada + Activo Fijo**: Depr.Acum.* para todos los activos fijos | ~40+ | Medio |
| 17 | **Agregar familia IVA/Impuestos**: IVA D.F, PPM, Impuesto Unico, ILA, etc. | ~20+ | Bajo |
| 18 | **Agregar familia Sueldos**: Vacaciones Proporcionales, Horas Extras, Indemnizaciones, Colación | ~20+ | Bajo |
| 19 | **Agregar familia Prestamos Bancarios**: Ptmo.*, Linea Credito* para Security, BICE, Corpbanca | ~20+ | Bajo |
| 20 | **Agregar familia Gastos Operacionales**: Fletes, Combustibles, Energía Eléctrica, Correo, Teléfono | ~25+ | Bajo |

### Resumen de impacto acumulado

| Categoría | Ganancia |
|-----------|----------|
| Solo alias en GS (1-10) | ~+105 |
| Matchers mejorados (11-14) | ~+1.011 |
| Diccionario completo (15-20) | ~+155 |
| **Impacto total potencial** | **~+1.271 (cobertura 47,3%)** |

---

## Conclusión

El sistema tiene un **potencial inmediato de duplicar su cobertura** (de 23,6% a 42,5%) sin escribir reglas manuales, solo mejorando los matchers del Learning Engine para que sean:

1. **Case-insensitive** (ignorar mayúsculas/minúsculas en nombres)
2. **Substring-aware** (coincidencia parcial, ej: "Gastos de Oficina" ↔ "Gastos de Oficina (O)")
3. **Fuzzy > 0.85** (variaciones ortográficas menores)
4. **Auto-aprendizaje de códigos repetidos** (mismo código en N empresas → aprender automáticamente)
5. **Población masiva de GS** desde las 633 cuentas con código repetido y las 2.087 cuentas reales únicas identificadas

La mayor ganancia individual viene de mejorar el matcher por **substring** (+612) y el **auto-aprendizaje por código repetido** (+316), que juntos representan el **92% del total** de ganancia estimada.
