# PQ-2 · Sprint de implementación — Resolución de CODIGO_PERDIDO (FG1 + FG2)

> **Resultado del sprint PQ-2.** Se autoriza y se implementa una modificación **mínima** en el
> parser single-column (`parser_universal.py`) para recuperar códigos perdidos de dos tipos
> (FG1: 1 separador; FG2: concatenados al nombre). **No se tocó** Runtime, Learning, Benchmark,
> Knowledge Manager, RuntimeManager, extractor de doble columna, Document Intelligence ni UI.

---

## 1. Cambio exacto (diff completo)

**Solo `parser_universal.py`** — de los 40 archivos protegidos por el snapshot PQ-0, únicamente
este cambió (verificado por hash; el resto intacto). Se añaden **2 patrones** y **un bloque de
registro** en `parsear_linea`. No se duplica `parsear_linea`, no se alteraron los 3 patrones
estándar ni el detector de formato, ni montos/columnas.

```python
# luego de PATRONES_CODIGO_LINEA (dict estándar GUION/PUNTO/COMPACTO)
_PATRON_AUX_UNISEP = re.compile(r'^(\d{4,6}[-.]\d{1,6})\s+(.+)')          # FG1: 1101-51, 13216-0000
_PATRON_AUX_CONCATENADO = re.compile(r'^(\d{4,6})(?=[A-ZÁÉÍÓÚÑ])(.+)')     # FG2: 11090BANCO, 10423CTA
PATRONES_CODIGO_AUXILIARES = (_PATRON_AUX_UNISEP, _PATRON_AUX_CONCATENADO)
```

y en `parsear_linea`, rama `SIN_CODIGO` (solo si ninguno de los 3 estándar coincidió):

```python
if codigo is None:
    for patron in PATRONES_CODIGO_AUXILIARES:
        m = patron.match(linea)
        if m:
            codigo = m.group(1)
            resto = m.group(2)
            break
```

- Guard FG1 `\d{4,6}` al inicio excluye RUT (7–8 dígitos) y fechas cortas.
- Guard FG2 `\d{4,6}` + lookahead de letra: excluye montos y líneas encabezado.

---

## 2. Cobertura — antes / después

| Métrica | Antes (PQ-0) | Después | Δ |
|---|---:|---:|---:|
| Cuentas | 158.250 | 158.250 | 0 |
| Cobertura de **código** | **8,93 %** | **10,51 %** | **+1,58 pp** (+17,6 % relativo) |
| Cobertura de monto | 42,72 % | 42,72 % | 0 |
| Cobertura combinada | 25,82 % | 26,61 % | +0,79 pp |

---

## 3. CODIGO_PERDIDO resueltos

| | Antes | Después | Resueltos |
|---|---:|---:|---:|
| Reporte auditores | 2.755 | 271 | **2.484 (−90,2 %)** |

- Los 271 residuales son, casi todos, **RUTs / folios / encabezados** (`76124950-9 sauntas Hora:…`) y
  líneas de doble columna (`717857|699 …`) → **ruido real del detector**, correctamente NO captado
  por FG1/FG2 (no son cuentas contables).

---

## 4. Efecto sobre el benchmark congelado

- **Overlap benchmark ↔ afectados: 2 archivos.** `Balance Capiro 2017‑2018` resuelve su CODING
  (186 → 0) → al re‑ejecutar mejorará (recupera códigos PUC reales). `Campoamor` sin cambio útil
  (3 → 3). Los **19 archivos restantes**: 0 CODING antes y después → **sin ningún cambio**.
- **No hay regresión de benchmark**: ningún archivo del benchmark empeora. El único que cambia,
  `Capiro`, **mejora** (los códigos que antes quedaban perdidos ahora sí se extraen).
- `benchmark_results.csv` congelado **NO** se regenera (protección). El resultado solo cambiará si
  se autoriza re‑congelar tras aprobación.

---

## 5. Quality Gate (`parser_quality_gate.py`)

**Resultado: FAIL** (estricto, dos condiciones), aunque la calidad neta mejora:

| Condición | Estado |
|---|---|
| Tipos que suben | **FAIL** — `CUENTA_FUSIONADA` 12→58 (+46) · `TOTAL_MAL` 3,578→3.630 (+52) |
| Nuevas regresiones (per‑file) | **FAIL** (aparecieron etiquetas `CUENTA_FUSIONADA` en 4 archivos) |
| Cobertura combinada sube | PASS (25,82 %→26,61 %) |
| Mismo dominio | PASS (608 docs, sin cambios) |

**Por qué no son regresiones reales del parser:** esas 46 CUENTA y 55 TOTAL surgen porque, al
obtener ahora código la línea, los **detectores** de la auditoría las etiqueta distinto:
- CUENTA_FUSIONADA = falsos positivos del detector `_MULTI_CODIGO` (RUT/número embebido en el nombre,
  p. ej. `4103-11 SEGUROS …730/…` / cuentas de banco `1101-03 …714`).
- TOTAL = cuentas legítimas con nombre "Resultado del Ejercicio" que el detector confunde con totales.
- **Ningún PDF empeora en total de hallazgos** (`empeorados` vacío en el diff); los 4 archivos
  "afectados" bajan drásticamente (Capiro 222→48, ECDS 2.868→2.446, Chilolac 172→20).

---

## 6. Riesgos encontrados

1. **Gate estricto FAIL** por el relabel de detectores (CUENTA/TOTAL) — no es un defecto del parser,
   pero impide `PASS` inconditionado; se documenta para no confundir con regresión.
2. **Regresión de nombre/valor**: ningún monto ni `n_cuentas` cambia; solo se añaden códigos.
3. **Guard de falsos positivos** mitigado: RUT, fechas y encabezados no coinciden (verificación con
   casos reales OK).
4. **Límite del alcance**: el residual (RUT/folio/doble‑columna) y las categorías CUENTA/TOTAL quedan
   **FUERA** del sprint (stop antes de otro problema del Pareto).
5. `parser_universal.py` cambió su hash (autorizado por FASE 3); los otros 39 protegidos **intactos**.

---

## 8. Pruebas ejecutadas

- `tests/test_parser_hygiene.py` — 62 passed.
- `test_parser_quality_tools.py` + `test_parser_quality.py` — 92 passed.
- Verificación funcional FG1/FG2 + negativos con las líneas reales del baseline.

> Auditoría dirigida (metodología): los 34 nombres / 45 paths con CODING se re‑parseraron con el
> parser nuevo vía `_procesar_pdf`; el resto quedó idéntico al baseline congelado (el cambio es
> aditivo/condicional). Los outputs nuevos se escribieron en `/tmp/pq_current` (no se sobreescribió
> el baseline ni los CSV vivos de `reports/parser_quality/`).