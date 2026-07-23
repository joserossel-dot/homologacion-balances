# Decision Trace Report

Generated: 2026-07-09 16:55:20 UTC

## Summary

| Metric | Value |
|---|---|
| Total Accounts | 10,672 |
| Classified | 1,892 |
| UNKNOWN | 8,780 |
| Classify Rate | 17.7% |

## Decision Code Distribution

| Code | Count | % |
|---|---|---|
| Unknown Variant | 8,780 | 82.3% |
| Exact Variant | 1,049 | 9.8% |
| Fuzzy Match | 448 | 4.2% |
| Dictionary Match | 228 | 2.1% |
| Manual Rule | 167 | 1.6% |

## Layout Distribution

| Layout | Total | Classified | UNKNOWN | % |
|---|---|---|---|---|
| validacion | 5,369 | 1,335 | 4,034 | 50.3% |
| edge_cases | 5,303 | 557 | 4,746 | 49.7% |

## Match Type Distribution

| Type | Count | % |
|---|---|---|
| none | 8,189 | 76.7% |
| cmcc_exact | 1,049 | 9.8% |
| shadow | 591 | 5.5% |
| dictionary | 521 | 4.9% |
| fuzzy | 167 | 1.6% |
| cmcc_fuzzy | 155 | 1.5% |

## Parser Status

| Status | Count | % |
|---|---|---|
| REJECT | 8,780 | 82.3% |
| ACCEPT | 1,892 | 17.7% |

## Top Concepts

| Concept | Count |
|---|---|
| AC.01 (shadow) | 296 |
| ER.04 | 255 |
| ANC.01 | 161 |
| AC.07 | 141 |
| ER.01 (shadow) | 130 |
| AC.01 | 119 |
| PAT.03 | 116 |
| PC.06 | 106 |
| PAT.01 | 105 |
| ER.09 | 94 |
| PAT.01 (shadow) | 82 |
| PAT.04 | 72 |
| ER.01 | 71 |
| PC.05 | 69 |
| PC.01 | 62 |

## Top Documents by Volume

| Document | Accounts |
|---|---|
|  | 10,672 |

## Sample UNKNOWN Traces

```
Rengo
├─ Normalized: rengo
├─ Parser: REJECT (confidence=0.0)
├─ Layout: edge_cases
├─ Shadow CMCC: ER.01
└─ Decision: [Unknown Variant] Sin coincidencia en código ni diccionario
```

```
1 Desde Enero Hasta Diciembre de
├─ Normalized: 1 desde enero hasta diciembre de
├─ Parser: REJECT (confidence=0.0)
├─ Layout: edge_cases
├─ No Match: Sin coincidencia en código ni diccionario
└─ Decision: [Unknown Variant] Sin coincidencia en código ni diccionario
```

```
CAJA 5.519,080 PROVEEDORES
├─ Normalized: caja 5.519,080 proveedores
├─ Parser: REJECT (confidence=0.0)
├─ Layout: edge_cases
├─ No Match: Sin coincidencia en código ni diccionario
└─ Decision: [Unknown Variant] Sin coincidencia en código ni diccionario
```

```
CAJA CHICA 100.000 CUENTAS POR PAGAR EMPRESA RELACION
├─ Normalized: caja chica 100.000 cuentas por pagar empresa relacion
├─ Parser: REJECT (confidence=0.0)
├─ Layout: edge_cases
├─ No Match: Sin coincidencia en código ni diccionario
└─ Decision: [Unknown Variant] Sin coincidencia en código ni diccionario
```

```
BANCO CORPBANCA CTA. 2 . 1,495,155 CTA CTE CONSIGNADOR
├─ Normalized: banco corpbanca cta. 2 . 1,495,155 cta cte consignador
├─ Parser: REJECT (confidence=0.0)
├─ Layout: edge_cases
├─ No Match: Sin coincidencia en código ni diccionario
└─ Decision: [Unknown Variant] Sin coincidencia en código ni diccionario
```


## Sample Classified Traces

```
CUENTAS POR COBRAR
├─ Normalized: cuentas por cobrar
├─ Parser: ACCEPT (confidence=0.8)
├─ Layout: edge_cases
├─ CMCC: exact → AC.03
└─ Decision: [Exact Variant] Gold Standard (exact) → AC.03 (matched: CUENTAS POR COBRAR)
```

```
REYALORIZACION CAPITAL PROPIO
├─ Normalized: reyalorizacion capital propio
├─ Parser: ACCEPT (confidence=0.8)
├─ Layout: edge_cases
├─ CMCC: fuzzy → PAT.01
└─ Decision: [Fuzzy Match] Gold Standard (fuzzy) → PAT.01 (matched: Revalorizacion Capital Propio)
```

```
MUEBLES Y UTILES
├─ Normalized: muebles y utiles
├─ Parser: ACCEPT (confidence=0.8)
├─ Layout: edge_cases
├─ CMCC: exact → ANC.01
└─ Decision: [Exact Variant] Gold Standard (exact) → ANC.01 (matched: MUEBLES Y UTILES)
```

```
INSTALACIONES
├─ Normalized: instalaciones
├─ Parser: ACCEPT (confidence=0.8)
├─ Layout: edge_cases
├─ CMCC: exact → ANC.01
└─ Decision: [Exact Variant] Gold Standard (exact) → ANC.01 (matched: Instalaciones)
```

```
¡ Ventas
├─ Normalized: ¡ ventas
├─ Parser: ACCEPT (confidence=0.8)
├─ Layout: edge_cases
├─ CMCC: exact → PAT.01
└─ Decision: [Exact Variant] Gold Standard (exact) → PAT.01 (matched: Ventas)
```

---
*No pipeline files were modified. Shadow mode only.*