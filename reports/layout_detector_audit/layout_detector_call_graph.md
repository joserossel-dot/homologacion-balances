# Call Graph: `parsers/layout_detector.py`

## Árbol de imports

```
parsers/layout_detector.py
├── import re                         (stdlib)
├── from dataclasses import dataclass, field  (stdlib)
└── from typing import Any           (stdlib)

→ Sin dependencias internas del proyecto.
→ No importa ningún módulo de parser_universal, parsers/, ni app_validacion.
```

## ¿Quién importa LayoutDetector?

```
parsers/__init__.py:20
  from parsers.layout_detector import DetectedLayout, LayoutDetector
  └── Solo re-exporta. No instancia ni llama.

parsers/pdf_parser.py:34
  from parsers.layout_detector import DetectedLayout, LayoutDetector
  └── Instancia en línea 84: self._layout_detector = LayoutDetector()
  └── Llama en línea 133: layout = self._layout_detector.detect(lineas)

scripts/run_parser_stress_test.py:501,507
  └── Solo mención textual en comentario de reporte.
  └── No importa ni instancia LayoutDetector.
```

## Flujo de llamadas actual (HOY)

```
ParserCore2.__init__(config)
  → LayoutDetector()                              # pdf_parser.py:84

ParserCore2.parse(path)
  → validar_archivo(path)                         # pdf_parser.py:100
  → _v1_parser._extraer_lineas(path)              # pdf_parser.py:114
      └── pdfplumber.open → page.extract_text()   # parser_universal.py:617-622
  → LayoutDetector.detect(lineas)                 # pdf_parser.py:133
      ├── _find_header_candidates(header_lines)   # layout_detector.py:106
      │     └── re.search(pattern, line_lower)     # layout_detector.py:122
      ├── _resolve_order(candidates)              # layout_detector.py:129
      └── DetectedLayout(...)                     # layout_detector.py:37
  → detectar_formato_codigo(primer_tokens)        # pdf_parser.py:144
  → detectar_separador_miles(muestra_montos)      # pdf_parser.py:146
  → parsear_todas(lineas, formato, separador)      # pdf_parser.py:150
      └── parsear_linea()                          # line_parser.py:42
            └── _parsear_linea()                    # parser_universal.py:430
                  └── ULTIMAS_COLS [-k:]             # parser_universal.py:510-527
  → ParseResult(layout=layout, ...)                # pdf_parser.py:182
```

## Flujo diseñado (lo que DEBERÍA pasar)

```
ParserCore2.parse(path)
  → ... (igual hasta línea 133)
  → LayoutDetector.detect(lineas)
      → DetectedLayout(columns=["activo", "pasivo", "perdida", "ganancia"])
  → parsear_todas(lineas, formato, separador, LAYOUT=layout)    # ← NUEVO
      └── parsear_linea(linea, ..., column_map=layout.columns)   # ← NUEVO
            └── Usar column_map en vez de ULTIMAS_COLS
  → ParseResult(layout=layout, accounts=cuentas, ...)
```

## Punto de conexión exacto

| Desde | Hacia | Dónde conectar |
|-------|-------|---------------|
| `parsers/pdf_parser.py:133` | `layout = self._layout_detector.detect(lineas)` | ✅ YA CONECTADO |
| `parsers/pdf_parser.py:137-139` | Comentario "Por ahora, se registra como métrica" | 🔴 AQUÍ FALTA |
| `parsers/pdf_parser.py:150` | `cuentas = parsear_todas(lineas, ...)` | 🔴 PASAR layout aquí |
| `parsers/line_parser.py:89-101` | `parsear_todas()` → `parsear_linea()` | 🔴 PASAR column_map aquí |
| `parser_universal.py:510-527` | `ULTIMAS_COLS` + loop de asignación | 🔴 REEMPLAZAR con column_map |

## LayoutDetector NO es llamado desde

| Módulo | Estado |
|--------|--------|
| `app_validacion.py` | ❌ Nunca |
| `pipeline/homologation_pipeline.py` | ❌ Nunca — usa `ParserPDF()` directamente |
| `pipeline/new_pipeline.py` | ❌ Nunca — usa `ParserPDF()` directamente |
| `parser_universal.py` | ❌ Nunca — monolito v1 |
| `scripts/` (excepto stress test) | ❌ Solo mención textual |
| `tools/` | ❌ Usan su propia lógica de layout en `tools/layout_audit.py` |
| `tests/` | ❌ No existen tests para parsers/ |
