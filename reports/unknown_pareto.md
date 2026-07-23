# Unknown Accounts Pareto — Post Sprint 28.5A

**Date:** 2026-07-22  

**Contexto:** 10541 cuentas UNKNOWN (tras filtrar 537 ruido de parseo) después de migrar 7 reglas regex con precisión 100%.

---

## Resumen

| Métrica | Valor |
|---|---|
| Total cuentas extraídas | 11696 |
| Clasificadas | 1155 |
| UNKNOWN (bruto) | 10541 |
| Ruido filtrado (fechas/headers) | 537 |
| UNKNOWN (neto analizable) | 10541 (90.12%) |
| Familias detectadas | 3894 |
| Familias con ≥10 cuentas | 149 |
| Familias con ≥5 cuentas | 399 |

## UNKNOWN por tipo de cuenta

| Tipo | Cuentas | % del total UNKNOWN |
|---|---|---|
| ACTIVO | 3435 | 34.34% |
| DESCONOCIDO | 3000 | 29.99% |
| PERDIDA | 1555 | 15.54% |
| PASIVO | 1406 | 14.05% |
| PATRIMONIO | 608 | 6.08% |

## Pareto — Top 50 Familias

| Rank | Familia | Count | % | % Acum | Tipos | Código Esperado | Regex Legacy | Dificultad |
|---|---|---|---|---|---|---|---|
| 1 | UTILIDAD EJERCICIO | 58 | 0.55% | 0.55% | PERDIDA | PAT.04 | PAT.04 | BAJA |
| 2 | CENTRALIZACION SUELDOS ADMINISTRACION SUELDOS | 43 | 0.41% | 0.96% | PASIVO | PC.06 | PC.06 | MEDIA |
| 3 | CUENTAS PAGAR ENTIDADES RELACIONADAS CORRIENTES | 39 | 0.37% | 1.33% | ACTIVO | AC.03 | AC.03, AC.06 | BAJA |
| 4 | REMUNERACIONES | 38 | 0.36% | 1.69% | PASIVO | PC.06 | PC.06 | MEDIA |
| 5 | OTROS PASIVOS FINANCIEROS CORRIENTES | 37 | 0.35% | 2.04% | PASIVO | PC.03 | N/A | ALTA |
| 6 | CAJA | 34 | 0.32% | 2.36% | ACTIVO | AC.01 | AC.01 | BAJA |
| 7 | ACUMULADO HASTA | 34 | 0.32% | 2.68% | PATRIMONIO | PAT.03 | N/A | MEDIA |
| 8 | CORRECCION MONETARIA | 33 | 0.31% | 2.99% | ACTIVO, DESCONOCIDO | ER.11 | N/A | MEDIA |
| 9 | CAPITAL | 33 | 0.31% | 3.3% | PATRIMONIO | PAT.01 | PAT.01 | BAJA |
| 10 | UTILIDADES ACUMULADAS | 32 | 0.3% | 3.6% | DESCONOCIDO, PATRIMONIO | PAT.03 | PAT.03 | BAJA |
| 11 | MARGEN EXPLOTACION | 31 | 0.29% | 3.89% | PERDIDA | ER.02 | N/A | MEDIA |
| 12 | DOCUMENTOS CUENTAS PAGAR EMPRESAS RELACIONADAS | 27 | 0.26% | 4.15% | ACTIVO | AC.03 | AC.03, ANC.05 | BAJA |
| 13 | CAPITAL EMITIDO | 27 | 0.26% | 4.41% | PATRIMONIO | PAT.01 | PAT.01 | BAJA |
| 14 | OTROS ACTIVOS FINANCIEROS CORRIENTES | 27 | 0.26% | 4.67% | ACTIVO | ANC.01 | N/A | ALTA |
| 15 | DEPRECIACION | 26 | 0.25% | 4.92% | ACTIVO | ER.07 | ER.07 | BAJA |
| 16 | DEUDORES VARIOS | 25 | 0.24% | 5.16% | ACTIVO | AC.07 | AC.07 | MEDIA |
| 17 | PROVEEDORES | 25 | 0.24% | 5.4% | PASIVO | PC.01 | PC.01 | BAJA |
| 18 | FLETES | 25 | 0.24% | 5.64% | PERDIDA | POR_DEFINIR | N/A | MEDIA |
| 19 | HONORARIOS | 24 | 0.23% | 5.87% | PASIVO | PC.06 | N/A | MEDIA |
| 20 | MUEBLES UTILES | 24 | 0.23% | 6.1% | ACTIVO | ANC.01 | ANC.01 | BAJA |
| 21 | GASTOS VIAJE REPRESENTACION | 24 | 0.23% | 6.33% | PERDIDA | ER.04 | N/A | MEDIA |
| 22 | CUENTAS PAGAR | 24 | 0.23% | 6.56% | ACTIVO, DESCONOCIDO | PC.01 | N/A | MEDIA |
| 23 | HONORARIOS PAGAR | 24 | 0.23% | 6.79% | DESCONOCIDO, PASIVO | PC.06 | PC.06 | MEDIA |
| 24 | DEUDORES COMERCIALES OTRAS CUENTAS COBRAR | 24 | 0.23% | 7.02% | ACTIVO | AC.03 | AC.03 | BAJA |
| 25 | ACTIVOS IMPUESTOS CORRIENTES | 24 | 0.23% | 7.25% | ACTIVO | AC.07 | N/A | MEDIA |
| 26 | RENGO | 23 | 0.22% | 7.47% | DESCONOCIDO | POR_DEFINIR | N/A | MEDIA |
| 27 | IMPUESTOS PAGAR | 23 | 0.22% | 7.69% | DESCONOCIDO, PASIVO | PC.05 | PC.05 | MEDIA |
| 28 | EFECTIVO EQUIVALENTES EFECTIVO | 23 | 0.22% | 7.91% | ACTIVO | AC.01 | N/A | MEDIA |
| 29 | PROPIEDADES PLANTAS EQUIPOS | 23 | 0.22% | 8.13% | ACTIVO | ANC.01 | ANC.01 | BAJA |
| 30 | CUENTAS COMERCIALES OTRAS CUENTAS PAGAR | 23 | 0.22% | 8.35% | PERDIDA | ER.05 | N/A | MEDIA |
| 31 | CAPITAL PAGADO | 22 | 0.21% | 8.56% | DESCONOCIDO, PATRIMONIO | PAT.01 | PAT.01 | BAJA |
| 32 | ELECTRICIDAD | 22 | 0.21% | 8.77% | DESCONOCIDO | POR_DEFINIR | N/A | MEDIA |
| 33 | VENTAS | 22 | 0.21% | 8.98% | PERDIDA | ER.01 | ER.01 | BAJA |
| 34 | CAPITAL SOCIAL | 21 | 0.2% | 9.18% | PATRIMONIO | PAT.01 | PAT.01 | BAJA |
| 35 | IMPUESTOS RECUPERAR | 21 | 0.2% | 9.38% | PASIVO | AC.07 | AC.07 | MEDIA |
| 36 | INGRESOS ACTIVIDADES ORDINARIAS | 21 | 0.2% | 9.58% | ACTIVO | POR_DEFINIR | N/A | MEDIA |
| 37 | REVALORIZACION CAPITAL PROPIO | 20 | 0.19% | 9.77% | ACTIVO, PATRIMONIO | PAT.01 | PAT.01 | BAJA |
| 38 | MATERIALES ASEO | 20 | 0.19% | 9.96% | ACTIVO | AC.05 | N/A | MEDIA |
| 39 | REAJUSTE PPM IVA | 20 | 0.19% | 10.15% | ACTIVO, DESCONOCIDO | AC.07 | AC.07 | MEDIA |
| 40 | SEGUROS | 20 | 0.19% | 10.34% | ACTIVO, DESCONOCIDO, PASIVO | POR_DEFINIR | N/A | MEDIA |
| 41 | OTRAS RESERVAS | 20 | 0.19% | 10.53% | PATRIMONIO | PAT.02 | PAT.02 | MEDIA |
| 42 | SEGURO CESANTIA | 19 | 0.18% | 10.71% | ACTIVO, DESCONOCIDO, PATRIMONIO | POR_DEFINIR | N/A | MEDIA |
| 43 | INTERESES BANCARIOS | 19 | 0.18% | 10.89% | ACTIVO | AC.01 | AC.01, ER.09 | BAJA |
| 44 | INSTALACIONES | 19 | 0.18% | 11.07% | DESCONOCIDO | POR_DEFINIR | N/A | MEDIA |
| 45 | PATENTE COMERCIAL VEHICULOS | 19 | 0.18% | 11.25% | ACTIVO | ANC.01 | ANC.01, ANC.03 | BAJA |
| 46 | DISPONIBLE | 18 | 0.17% | 11.42% | DESCONOCIDO | AC.01 | AC.01 | BAJA |
| 47 | COMISIONES | 18 | 0.17% | 11.59% | PERDIDA | ER.09 | N/A | MEDIA |
| 48 | CUENTAS COBRAR | 18 | 0.17% | 11.76% | ACTIVO | AC.03 | AC.03 | BAJA |
| 49 | IMPRENTA | 18 | 0.17% | 11.93% | DESCONOCIDO | PC.05 | N/A | MEDIA |
| 50 | SERVICIO SEGURIDAD | 18 | 0.17% | 12.1% | ACTIVO | POR_DEFINIR | N/A | MEDIA |

## Top 10 Recomendados (menor riesgo, mayor impacto)

| # | Familia | Count | Código | Dificultad | Regex | Razón |
|---|---|---|---|---|---|
| 1 | UTILIDAD EJERCICIO | 58 | PAT.04 | BAJA | PAT.04 | Tiene regex legacy (PAT.04), tipo único |
| 2 | CUENTAS PAGAR ENTIDADES RELACIONADAS CORRIENTES | 39 | AC.03 | BAJA | AC.03, AC.06 | Tiene regex legacy (AC.03, AC.06), tipo único |
| 3 | CAJA | 34 | AC.01 | BAJA | AC.01 | Tiene regex legacy (AC.01), tipo único |
| 4 | CAPITAL | 33 | PAT.01 | BAJA | PAT.01 | Tiene regex legacy (PAT.01), tipo único |
| 5 | DOCUMENTOS CUENTAS PAGAR EMPRESAS RELACIONADAS | 27 | AC.03 | BAJA | AC.03, ANC.05 | Tiene regex legacy (AC.03, ANC.05), tipo único |
| 6 | CAPITAL EMITIDO | 27 | PAT.01 | BAJA | PAT.01 | Tiene regex legacy (PAT.01), tipo único |
| 7 | DEPRECIACION | 26 | ER.07 | BAJA | ER.07 | Tiene regex legacy (ER.07), tipo único |
| 8 | PROVEEDORES | 25 | PC.01 | BAJA | PC.01 | Tiene regex legacy (PC.01), tipo único |
| 9 | MUEBLES UTILES | 24 | ANC.01 | BAJA | ANC.01 | Tiene regex legacy (ANC.01), tipo único |
| 10 | DEUDORES COMERCIALES OTRAS CUENTAS COBRAR | 24 | AC.03 | BAJA | AC.03 | Tiene regex legacy (AC.03), tipo único |

---
*Generated by analyze_unknown_pareto.py*