# Reporte de Calidad del Parser — Parser Gatekeeper

**Fecha:** 2026-07-07 21:02:19

---

## Resumen General

- **Documentos procesados:** 186
- **Candidatos evaluados:** 30022
- **Confianza promedio:** 0.608

## Decisiones del Gatekeeper

| Decisión | Cuentas | % |
|----------|---------|---|
| ✅ ACCEPT | 3641 | 12.1% |
| ⚠️ REVIEW | 22456 | 74.8% |
| ❌ REJECT | 3925 | 13.1% |

## Confianza por Tipo de Documento

| Tipo | Documentos | Candidatos | Confianza Promedio |
|------|------------|------------|--------------------|
| 📄 Texto nativo | 138 | 20857 | 0.625 |
| 🖼️ OCR | 72 | 9165 | 0.569 |

## Top 10 Razones de Rechazo

| # | Razón | Ocurrencias |
|---|-------|-------------|
| 1 | `ocr_low_confidence` | 1548 |
| 2 | `name_too_many_digits` | 827 |
| 3 | `name_too_short` | 769 |
| 4 | `name_too_many_symbols` | 598 |
| 5 | `contains_date` | 486 |
| 6 | `name_only_symbols` | 351 |
| 7 | `contains_header` | 322 |
| 8 | `contains_address` | 304 |
| 9 | `name_too_long` | 191 |
| 10 | `contains_balance_general` | 188 |

## Top 10 Documentos con Más Rechazos

| # | Documento | Rechazos |
|---|----------|----------|
| 1 | ECDS Balance 10-2020 (1).pdf | 334 |
| 2 | Balance Xpovin.pdf | 176 |
| 3 | balance tributario dic 2020 agr tuqui.xlsx | 159 |
| 4 | EEFF 16 - RENTAS 17 - GRUPO CASA GARCIA.pdf | 145 |
| 5 | BALANCE CLASIFICADO CENTRAL 2019.pdf | 104 |
| 6 | BALANCE ORIGINAL 2014.pdf | 93 |
| 7 | Pre-Balance al 31-12-2020_TRANSPORTES JG_76350177-9 .xlsx | 85 |
| 8 | balance cm 2017.pdf | 70 |
| 9 | Balance Capiro 2017-2018.pdf | 64 |
| 10 | Balance Exportadora Gonzagri.pdf | 64 |

## Top 10 Documentos con Menor Confianza Promedio

| # | Documento | Confianza Prom. |
|---|-----------|-----------------|
| 1 | BALANCE CLASIFICADO CENTRAL 2019.pdf | 0.224 |
| 2 | Balance Inmob 2015.pdf | 0.373 |
| 3 | Balance Asipac 2015.pdf | 0.397 |
| 4 | Balance Sup Central 2015.pdf | 0.408 |
| 5 | Balance Mega 2015.pdf | 0.411 |
| 6 | balance tributario dic 2020 agr tuqui.xlsx | 0.451 |
| 7 | Pre-Balance al 31-12-2020_TRANSPORTES JG_76350177-9 .xlsx | 0.451 |
| 8 | Balance Xpovin.pdf | 0.458 |
| 9 | Balance Capiro 2017-2018.pdf | 0.478 |
| 10 | Balance 2018 con firma.pdf | 0.483 |

## Distribución de Confianza

| Rango | Cuentas |
|-------|---------|
| 0.00-0.25 | 949 ██
| 0.25-0.50 | 2976 ███████
| 0.50-0.70 | 16376 ████████████████████████████████████████
| 0.70-0.85 | 6080 ██████████████
| 0.85-1.00 | 3641 ████████
| 1.00 | 0 █
