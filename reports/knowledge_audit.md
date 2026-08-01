# Auditoría de Knowledge Base CMCC

**Generado:** `2026-07-27T10:27:47.584770`
**Fuente:** `knowledge_base/cmcc_knowledge.json`

---

## Resumen

| Métrica | Valor |
|---------|-------|
| Total códigos CMCC | 30 |
| Total variantes | 163 |
| Total familias | 6 |
| Variantes conflictivas | 1 |
| Códigos con baja evidencia | 19 |
| Códigos recomendados para revisión | 20 |

**Códigos recomendados para revisión:** AC.01, AC.03, AC.05, AC.06, AC.06S, AC.07, ANC.01, ANC.03, ANC.07, ER.04, ER.09, ER.14, PAT.02, PAT.04, PC.01, PC.04, PC.06, PNC.01, PNC.04, anticipo a proveedores

**Problemas totales detectados:** 29

---

## 1. Códigos CMCC duplicados

_Sin duplicados._

---

## 2. Variantes repetidas

_Sin variantes repetidas exactas._

---

## 3. Variantes asignadas a distintos códigos

| Normalizado | Códigos |
|-------------|---------|
| `anticipo a proveedores` | AC.01, AC.07 |

---

## 4. Códigos con muy poca evidencia

| Código | Frecuencia | Confianza | Variantes | Razones |
|--------|------------|-----------|-----------|---------|
| AC.01 | 22 | 0.0785 | 17 | confianza_baja(0.0785) |
| AC.03 | 14 | 0.1429 | 9 | confianza_baja(0.1429) |
| AC.05 | 7 | 0.1429 | 7 | confianza_baja(0.1429) |
| AC.06 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |
| AC.06S | 2 | 0.5 | 2 | frecuencia_baja(2) |
| AC.07 | 15 | 0.1289 | 10 | confianza_baja(0.1289) |
| ANC.01 | 21 | 0.093 | 13 | confianza_baja(0.0930) |
| ANC.03 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |
| ANC.07 | 2 | 1.0 | 1 | frecuencia_baja(2) |
| ER.04 | 22 | 0.1033 | 12 | confianza_baja(0.1033) |
| ER.09 | 12 | 0.1389 | 8 | confianza_baja(0.1389) |
| ER.14 | 2 | 1.0 | 1 | frecuencia_baja(2) |
| PAT.02 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |
| PAT.04 | 2 | 1.0 | 1 | frecuencia_baja(2) |
| PC.01 | 22 | 0.0744 | 18 | confianza_baja(0.0744) |
| PC.04 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |
| PC.06 | 21 | 0.102 | 12 | confianza_baja(0.1020) |
| PNC.01 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |
| PNC.04 | 1 | 1.0 | 1 | frecuencia_baja(1), registro_unico |

---

## 5. Familias incompletas

| Familia | Miembros | Frecuencia total | Razones |
|---------|----------|------------------|---------|
| PNC | 2 | 2 | pocos_miembros(2), baja_frecuencia_total(2) |

---

## 6. Inconsistencias de jerarquía

_Sin inconsistencias de jerarquía._

---

## 7. Variantes extremadamente similares con distinto código

| Variante A | Código A | Variante B | Código B | Similitud |
|------------|----------|------------|----------|-----------|
| Anticipo a Proveedores | AC.01 | Anticipos a Proveedores | AC.05 | 0.9778 |
| Prestamo Bancario Corto Plazo | PC.02 | Prestamo Bancario Largo Plazo | PNC.01 | 0.8966 |
| Intereses pagados | ER.09 | Intereses Ganados | ER.12 | 0.8824 |
| Gastos Pagados por Anticipado | AC.01 | SEGUROS PAGADOS POR ANTICIPADO | AC.07 | 0.8814 |
| Documentos por Pagar | PC.01 | Cuentas por Pagar | PC.07 | 0.8649 |
| Boletas en Garantia | AC.01 | Resp. Boletas en Garantia | ER.01 | 0.8636 |
| Iva Credito Fiscal | AC.07 | Iva Debito Fiscal | PC.05 | 0.8571 |
| OTROS IMPUESTOS POR RECUPERAR | AC.07 | OTROS IMPUESTOS POR PAGAR | PC.05 | 0.8519 |

---

## 8. Confianza promedio por código

**Promedio general:** 0.4624

| Código | Confianza |
|--------|-----------|
| AC.01 | 0.0785 |
| AC.03 | 0.1429 |
| AC.05 | 0.1429 |
| AC.06 | 1.0 |
| AC.06S | 0.5 |
| AC.07 | 0.1289 |
| ANC.01 | 0.093 |
| ANC.03 | 1.0 |
| ANC.06 | 0.25 |
| ANC.07 | 1.0 |
| ER.01 | 0.375 |
| ER.04 | 0.1033 |
| ER.07 | 0.375 |
| ER.09 | 0.1389 |
| ER.12 | 0.5556 |
| ER.13 | 0.375 |
| ER.14 | 1.0 |
| PAT.01 | 0.1528 |
| PAT.02 | 1.0 |
| PAT.03 | 0.375 |
| PAT.04 | 1.0 |
| PC.01 | 0.0744 |
| PC.02 | 0.1837 |
| PC.04 | 1.0 |
| PC.05 | 0.1667 |
| PC.06 | 0.102 |
| PC.07 | 0.3333 |
| PC.08 | 0.2245 |
| PNC.01 | 1.0 |
| PNC.04 | 1.0 |

---

## 9. Confianza promedio por familia

**Promedio general:** 0.5442

| Familia | Confianza promedio | Miembros |
|---------|-------------------|----------|
| AC | 0.3322 | 6 |
| ANC | 0.5857 | 4 |
| ER | 0.4175 | 7 |
| PAT | 0.632 | 4 |
| PC | 0.2978 | 7 |
| PNC | 1.0 | 2 |

---

## 10. Cobertura del Gold Standard

| Métrica | Valor |
|---------|-------|
| Códigos en Gold Standard | 30 |
| Códigos en Knowledge Base | 30 |
| Códigos cubiertos | 30 |
| Cobertura | 100.0% |
| Registros en Gold Standard | 234 |


---

## Resumen de problemas

| Categoría | Total |
|-----------|-------|
| Códigos duplicados | 0 |
| Variantes repetidas | 0 |
| Variantes cross-code | 1 |
| Códigos baja evidencia | 19 |
| Familias incompletas | 1 |
| Inconsistencias jerarquía | 0 |
| Variantes similares cross-code | 8 |

*Auditoría generada por knowledge_base/audit.py*