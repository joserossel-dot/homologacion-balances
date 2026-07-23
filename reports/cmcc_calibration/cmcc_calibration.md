# CMCC Calibration Report

Generado: 2026-07-09 14:49:36 UTC

Total UNKNOWN analizados: **8,780**
OCR: 8780 | Nativo: 0

## Comparación de Umbrales

| Threshold | Recuperados | % | Restantes | Conceptos | OCR | Nativo |
|---|---|---|---|---|---|---|
| 1.00 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.99 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.98 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.97 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.95 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.90 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |
| 0.85 | 3,041 | 34.64% | 5,739 | 25 | 3,041 | 0 |

## Distribución de Scores

| Rango | Cuentas | % |
|---|---|---|
| 0.00-0.50 | 3,941 | 44.9% |
| 0.50-0.70 | 1,798 | 20.5% |
| 0.70-0.85 | 0 | 0.0% |
| 0.85-0.90 | 0 | 0.0% |
| 0.90-0.95 | 0 | 0.0% |
| 0.95-0.99 | 0 | 0.0% |
| 0.99-1.00 | 0 | 0.0% |
| 1.00-1.01 | 3,041 | 34.6% |

## Top Códigos Recuperados (threshold 0.90)

| # | Código | Concepto | Veces |
|---|---|---|---|
| 1 | AC.01 | Caja y Bancos | 1,926 |
| 2 | ER.01 | Ventas | 456 |
| 3 | ER.02 | Costo de Ventas | 283 |
| 4 | PAT.01 | Capital | 127 |
| 5 | PC.01 | Proveedores | 120 |
| 6 | ER.04 | Gastos de Administración | 29 |
| 7 | ANC.01 | Activo Fijo | 20 |
| 8 | ER.11 | Utilidad Neta | 11 |
| 9 | PC.05 | Impuestos por Pagar | 8 |
| 10 | PAT.04 | Resultado del Ejercicio | 8 |
| 11 | ER.13 | Otras Ganancias y Pérdidas | 7 |
| 12 | AC.08 | Otros Activos Corrientes | 7 |
| 13 | AC.05 | Inventarios | 6 |
| 14 | PC.08 | Otros Pasivos Corrientes | 5 |
| 15 | ER.05 | Gastos de Venta | 5 |

## Top Variantes Usadas (threshold 0.90)

| # | Variante | Veces |
|---|---|---|
| 1 | AL 31 DE DICIEMBRE | 28 |
| 2 | caja | 27 |
| 3 | Capital emitido | 25 |
| 4 | nivel | 25 |
| 5 | (=) MARGEN DE LA EXPLOTACION | 23 |
| 6 | Activos por impuestos corrientes | 23 |
| 7 | Ingresos de actividades ordinarias | 20 |
| 8 | Cuentas por pagar a entidades relacionadas, corrientes | 19 |
| 9 | Enero a Diciembre | 18 |
| 10 | fletes | 18 |
| 11 | Efectivo y equivalentes al efectivo | 18 |
| 12 | Otros activos no financieros, corrientes | 18 |
| 13 | DEPRECIACION ACUMULADA | 18 |
| 14 | Otros pasivos financieros no corrientes | 17 |
| 15 | Materiales de Aseo | 16 |

## Recuperación por Layout

| Layout | UNKNOWN | Recuperados (≥0.90) | % |
|---|---|---|---|
| edge_cases | 4,746 | 1,904 | 40.1% |
| validacion | 4,034 | 1,137 | 28.2% |

## OCR vs Nativo

| Tipo | UNKNOWN | Recuperados (≥0.90) | % |
|---|---|---|---|
| OCR | 8,780 | 3,041 | 34.6% |
| Nativo | 0 | 0 | 0% |

## Curva de Recuperación

| Threshold | Recuperados | % |
|---|---|---|
| 1.00 | 3,041 | 34.64% |
| 0.99 | 3,041 | 34.64% |
| 0.98 | 3,041 | 34.64% |
| 0.97 | 3,041 | 34.64% |
| 0.95 | 3,041 | 34.64% |
| 0.90 | 3,041 | 34.64% |
| 0.85 | 3,041 | 34.64% |

## Conclusiones

### 1. ¿Cuál threshold maximiza recuperación?
**1.00** — recupera **3,041** cuentas (34.64% del total UNKNOWN).

### 2. ¿Cuál threshold mantiene mayor precisión esperada?
**1.00** — recupera **3,041** cuentas (34.64%) con alta confianza (≥95%).

### 3. ¿Cuántas cuentas nuevas se clasificarían?
- **Threshold 0.95**: 3,041 cuentas nuevas
- **Threshold 0.90**: 3,041 cuentas nuevas
- **Threshold 0.85**: 3,041 cuentas nuevas

### 4. ¿Cuántas quedarían en REVIEW?
**0** cuentas en zona dudosa (0.70-0.90) requerirían revisión manual.

### 5. ¿Cuántas seguirían UNKNOWN?
- **Threshold 1.00**: 5,739 UNKNOWN persistentes
- **Threshold 0.95**: 5,739 UNKNOWN persistentes
- **Threshold 0.90**: 5,739 UNKNOWN persistentes
- **Threshold 0.85**: 5,739 UNKNOWN persistentes

### 6. ¿Qué conceptos dominan?
1. **Caja y Bancos** (AC.01): 1,926 veces
2. **Ventas** (ER.01): 456 veces
3. **Costo de Ventas** (ER.02): 283 veces
4. **Capital** (PAT.01): 127 veces
5. **Proveedores** (PC.01): 120 veces

### 7. ¿Qué layouts recuperan más?
- **edge_cases**: 1,904/4,746 (40.1%)
- **validacion**: 1,137/4,034 (28.2%)

### 8. ¿Qué porcentaje corresponde a OCR?
- **100.0%** del total UNKNOWN son OCR (8,780 cuentas)
- Recuperación OCR al threshold 0.90: **34.6%**

### 9. Recomendación final
**Threshold recomendado: 1.00**

- Recupera **3,041** cuentas (34.64% del total UNKNOWN)
- Deja **5,739** UNKNOWN persistentes
- Hay **0** casos en zona dudosa para revisión manual
- Balance óptimo entre recuperación y precisión esperada
- Activación solo en shadow mode — sin impacto en clasificación oficial
