# Gold Standard v1 — Permanent Ground Truth

**Date:** 2026-07-22  
**Total accounts:** 2500  
**Source:** 182 PDF balances (stratified selection from 11,690 accounts)  

---

## Selection Criteria

1. **All 105 unique audit accounts** — manually verified ground truth
2. **DEv2 high-confidence** (score >= 0.9, consensus >= 2) — strong auto-classifications
3. **Type-balanced fill** — ACTIVO, PASIVO, PATRIMONIO, GANANCIA, PERDIDA quotas
4. **Ambiguous names** — same name across multiple files for cross-file validation
5. **OCR-difficult** — accounts with OCR artifacts (digit substitutions)
6. **Unknown/hard cases** — accounts no engine can classify (for human review)

---

## Summary

| Metric | Value |
|---|---|
| Total | 2500 |
| With code assigned | 2400 (96.0%) |
| Pending review | 100 (4.0%) |

### By Account Type

| Type | Count | % |
|---|---|---|
| ACTIVO | 638 | 25.5% |
| PASIVO | 499 | 20.0% |
| PERDIDA | 476 | 19.0% |
| ACTIVO NO CORRIENTE | 366 | 14.6% |
| PATRIMONIO | 229 | 9.2% |
| GANANCIA | 169 | 6.8% |
| DESCONOCIDO | 102 | 4.1% |
| PASIVO NO CORRIENTE | 21 | 0.8% |

### By Resolution Method

| Method | Count | % |
|---|---|---|
| de_v2_medium_score | 1023 | 40.9% |
| de_v2_low | 415 | 16.6% |
| de_v2_consensus | 407 | 16.3% |
| de_v2_high_score | 378 | 15.1% |
| de_v2_strong_consensus | 107 | 4.3% |
| unknown | 100 | 4.0% |
| audit_regex | 35 | 1.4% |
| audit_sm | 35 | 1.4% |

### By Priority

| Priority | Count | % |
|---|---|---|
| Baja (confianza alta) | 584 | 23.4% |
| Media (verificar) | 1816 | 72.6% |
| Alta (requiere revision) | 100 | 4.0% |

### Top CMCC Codes

| Code | Count |
|---|---|
| ER.04 | 284 |
| ANC.01 | 280 |
| AC.01 | 262 |
| PC.06 | 244 |
| AC.03 | 142 |
| ER.01 | 125 |
| PAT.01 | 103 |
| AC.07 | 94 |
| PC.05 | 79 |
| PAT.03 | 66 |
| AC.05 | 62 |
| ER.09 | 59 |
| ANC.03 | 58 |
| PC.08 | 48 |
| ER.07 | 48 |
| PC.01 | 46 |
| ER.02 | 40 |
| PC.03 | 40 |
| PC.02 | 35 |
| PAT.04 | 34 |

---

## High Priority Accounts (need human review)

**100 accounts** where no reliable code could be auto-assigned:

| # | Account | Motivo |
|---|---|---|
| 1047 | Nivel | Ningun motor clasifica — requiere revision humana |
| 1048 | Desde Enero a Diciembre | Ningun motor clasifica — requiere revision humana |
| 1049 | GM ———omeccion AVDA. LOSCONQUISTADORES 1700 FOLIO UNICO NACI | Ningun motor clasifica — requiere revision humana |
| 1050 | O: ANIVEL | Ningun motor clasifica — requiere revision humana |
| 1051 | Desde 01/01/2014 — Al 3112014 NW” Folio | Ningun motor clasifica — requiere revision humana |
| 1052 | A _ — — á+>=>=+=—=2211 aa ed DOOM ANP FOdio | Ningun motor clasifica — requiere revision humana |
| 1053 | | GTA. CTE SOCIOS | Ningun motor clasifica — requiere revision humana |
| 1054 | l ANTICIFO PERSONAL: | Ningun motor clasifica — requiere revision humana |
| 1055 | e SALA CUNA | Ningun motor clasifica — requiere revision humana |
| 1056 | o FILES PLANTA | Ningun motor clasifica — requiere revision humana |
| 1057 | INSUMOS PLANTA | Ningun motor clasifica — requiere revision humana |
| 1058 | ad INSUMOS QUIMICOS | Ningun motor clasifica — requiere revision humana |
| 1059 | ARTICULOS DE ASEO | Ningun motor clasifica — requiere revision humana |
| 1060 | had : ROPA DE TRABAJO | Ningun motor clasifica — requiere revision humana |
| 1061 | E OBRAS B. INMUEBLE | Ningun motor clasifica — requiere revision humana |
| 1062 | OBRAS B. MUEBLES 108.963.751 4A80D00 — | Ningun motor clasifica — requiere revision humana |
| 1063 | SERV. DE TERCEROS | Ningun motor clasifica — requiere revision humana |
| 1064 | o OTROS GASTOS E | Ningun motor clasifica — requiere revision humana |
| 1065 | l Total Párina | Ningun motor clasifica — requiere revision humana |
| 1066 | o DIRECCION AVDA, LOS CONQUISTADORES 1700 FOLIO UNICO NACION | Ningun motor clasifica — requiere revision humana |
| 1067 | 0 —ANIVEL | Ningun motor clasifica — requiere revision humana |
| 1068 | Desde 01/01/2014 Al 31/12/2014 N' Folio | Ningun motor clasifica — requiere revision humana |
| 1069 | (AAA a 85d DIDIROMA ALA AN Folio | Ningun motor clasifica — requiere revision humana |
| 1070 | Dela Página Anterior | Ningun motor clasifica — requiere revision humana |
| 1071 | : BOMBAS Y MOTORES | Ningun motor clasifica — requiere revision humana |
| 1072 | : VARIOS DEUDORESLP. ' | Ningun motor clasifica — requiere revision humana |
| 1073 | | REMUNERACIONESPOR — 856.159.690 970.6050%4 | Ningun motor clasifica — requiere revision humana |
| 1074 | FONDOS CESANTIA | Ningun motor clasifica — requiere revision humana |
| 1075 | o. FONASA | Ningun motor clasifica — requiere revision humana |
| 1076 | EMDICATO | Ningun motor clasifica — requiere revision humana |
| 1077 | SEGUNDA CATEGORÍA | Ningun motor clasifica — requiere revision humana |
| 1078 | O Cs omecaioN AVDA. LOSCONQUISTADORES 1700 FOLIO UNICO NACIO | Ningun motor clasifica — requiere revision humana |
| 1079 | Oo. ANIVEL | Ningun motor clasifica — requiere revision humana |
| 1080 | Desde 01/01/2014 Aa 31/12/2014 N" Folio | Ningun motor clasifica — requiere revision humana |
| 1081 | _AAMMM>+=]=21029 mm de 01/00 A RON Folio | Ningun motor clasifica — requiere revision humana |
| 1082 | : De la Página Anterior | Ningun motor clasifica — requiere revision humana |
| 1083 | o PROV.COMPRA FRUTA | Ningun motor clasifica — requiere revision humana |
| 1084 | E FROVISION PLANTA | Ningun motor clasifica — requiere revision humana |
| 1085 | e PROVISION INTERESES | Ningun motor clasifica — requiere revision humana |
| 1086 | PERDIDAS Y GANANCIAS — | Ningun motor clasifica — requiere revision humana |
| 1087 | : RESERY AS LEGALES | Ningun motor clasifica — requiere revision humana |
| 1088 | MO. CONTRATISTA 339.294.130 221200 339.572.930 : | Ningun motor clasifica — requiere revision humana |
| 1089 | : HORASEXTRAS | Ningun motor clasifica — requiere revision humana |
| 1090 | o FERIADO PROPORCIONAL — 38.826.788 158.375 38.668.415 ] | Ningun motor clasifica — requiere revision humana |
| 1091 | : SEGURO CESANTÍA | Ningun motor clasifica — requiere revision humana |
| 1092 | SEGURO DE INVALIDEZ | Ningun motor clasifica — requiere revision humana |
| 1093 | E CASINO | Ningun motor clasifica — requiere revision humana |
| 1094 | TRANSPORTE PERSONAL — | Ningun motor clasifica — requiere revision humana |
| 1095 | o. ENSOBRADO Y PAGO | Ningun motor clasifica — requiere revision humana |
| 1096 | OTROS GASTOS DEL 997 682 ? 997.582 : | Ningun motor clasifica — requiere revision humana |
| 1097 | MANTENCION Y 103.795.303 108.793.303 : | Ningun motor clasifica — requiere revision humana |
| 1098 | pS LUBRICANTES | Ningun motor clasifica — requiere revision humana |
| 1099 | GAS LICUADO | Ningun motor clasifica — requiere revision humana |
| 1100 | RAZON SOC Pascicing y Servicios Rucsray | Ningun motor clasifica — requiere revision humana |
| 1101 | o. —ANIVEL | Ningun motor clasifica — requiere revision humana |
| 1102 | Desde 01/01/3014 — Al 31/12£0014 WN" Folio | Ningun motor clasifica — requiere revision humana |
| 1103 | Dela Página Anterior — | Ningun motor clasifica — requiere revision humana |
| 1104 | o IMPTO. COMBUSTIBLE 2.253.029 223309.” | Ningun motor clasifica — requiere revision humana |
| 1105 | QUIMICOS CEREZAS | Ningun motor clasifica — requiere revision humana |
| 1106 | INSUMOS QUIMICOS | Ningun motor clasifica — requiere revision humana |
| 1107 | 0 INSUMOS ARMADO | Ningun motor clasifica — requiere revision humana |
| 1108 | o ANALISISLABORATORIO-—— | Ningun motor clasifica — requiere revision humana |
| 1109 | | FUMIGACIONES "8321.80 | Ningun motor clasifica — requiere revision humana |
| 1110 | CAMARAS | Ningun motor clasifica — requiere revision humana |
| 1111 | ] TELEFONO RED FIA | Ningun motor clasifica — requiere revision humana |
| 1112 | O: TELEFONO CELULAR | Ningun motor clasifica — requiere revision humana |
| 1113 | CORRESPONDENCIA | Ningun motor clasifica — requiere revision humana |
| 1114 | E ARTICULOS LIBRERIA 6301958 77.080 6324878 : | Ningun motor clasifica — requiere revision humana |
| 1115 | PEAJES Y 1.127.329 Ñ | Ningun motor clasifica — requiere revision humana |
| 1116 | 0 PUBLICIDAD Y DIFUSION 279.997 279.997 ; | Ningun motor clasifica — requiere revision humana |
| 1117 | ARTICULOS ASEO 12.007.476 12.007.476 ) | Ningun motor clasifica — requiere revision humana |
| 1118 | EQUIPOS DE SEGURIDAD | Ningun motor clasifica — requiere revision humana |
| 1119 | o. ORNAMENTACION | Ningun motor clasifica — requiere revision humana |
| 1120 | o Total Pázina | Ningun motor clasifica — requiere revision humana |
| 1121 | 0 DIRECCION — AYDA. LOS CONQUISTADORES 1700 FOLIO UNICO NACI | Ningun motor clasifica — requiere revision humana |
| 1122 | o: ANIVEL | Ningun motor clasifica — requiere revision humana |
| 1123 | Desde 01/01/0014 Al 31/12/2014 W Folio | Ningun motor clasifica — requiere revision humana |
| 1124 | De la Página Anterior — | Ningun motor clasifica — requiere revision humana |
| 1125 | e FRIO 3.045414' | Ningun motor clasifica — requiere revision humana |
| 1126 | i ARMADO DE CAJAS | Ningun motor clasifica — requiere revision humana |
| 1127 | E IDENTIFICACION PALLET | Ningun motor clasifica — requiere revision humana |
| 1128 | HORASEXIRA | Ningun motor clasifica — requiere revision humana |
| 1129 | ss FERIADO PROPORCIONAL — | Ningun motor clasifica — requiere revision humana |
| 1130 | SEGURO CESANTIA | Ningun motor clasifica — requiere revision humana |
| 1131 | € CASINO | Ningun motor clasifica — requiere revision humana |
| 1132 | | "MANTENCION Y - 1219072 : | Ningun motor clasifica — requiere revision humana |
| 1133 | TELEFONO RED FIA | Ningun motor clasifica — requiere revision humana |
| 1134 | o TELEFONO CELULAR | Ningun motor clasifica — requiere revision humana |
| 1135 | E CORRESPONDENCIA | Ningun motor clasifica — requiere revision humana |
| 1136 | o. ARTICULOS LIBRERIA | Ningun motor clasifica — requiere revision humana |
| 1137 | o Total Página | Ningun motor clasifica — requiere revision humana |
| 1138 | O DIRECCION AVDA. LOS CONQUISTADORES 1700 FOLIO UNICO NACION | Ningun motor clasifica — requiere revision humana |
| 1139 | Desde 01/01/2014 Al 31/12/2014 NW” Folio | Ningun motor clasifica — requiere revision humana |
| 1140 | l De la Página Anterior | Ningun motor clasifica — requiere revision humana |
| 1141 | o PEAJES Y | Ningun motor clasifica — requiere revision humana |
| 1142 | | ARTICULOS ASEO | Ningun motor clasifica — requiere revision humana |
| 1143 | : VIATICOS Y PASAJES | Ningun motor clasifica — requiere revision humana |
| 1144 | : IVA FUERA DE PLAZO | Ningun motor clasifica — requiere revision humana |
| 1145 | O DIFERENCIA DECAMBIO > | Ningun motor clasifica — requiere revision humana |
| 1146 | SEGURO PLANTA 56.904.960 56I04960 ] | Ningun motor clasifica — requiere revision humana |

---

## Usage

This Gold Standard is the single source of truth for:
- Training precision/recall benchmarks
- Validating classifier improvements
- Detecting regression after catalog changes
- Human review prioritization

**Rules:**
- DO NOT modify auto-assigned codes without manual verification
- DO review high-priority (prioridad=1) accounts first
- DO rebuild after every concept catalog change
- DO NOT commit without at least 90% of priority-1 resolved

