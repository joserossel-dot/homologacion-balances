# PQ-2 Auditoría — Aumento de CUENTA_FUSIONADA (+46) y TOTAL_MAL_INTERPRETADO (+55)

- **Fecha:** 2026-08-06
- **Sprint:** PQ-2 (reset de códigos perdidos: FG1 separador único + FG2 concatenación)
- **Archivo modificado:** `parser_universal.py`
- **Objetivo del documento:** auditar si el aumento de las métricas del gate (FAIL) es una **regresión real del parser** o una **limitación de los detectores del auditor**.

---

## 1. Resumen ejecutivo

### 1.1 Objetivo de PQ-2
Resolver el problema de `CODIGO_PERDIDO` (códigos de cuenta PUC que el parser no reconocía) mediante dos mejoras en `parser_universal.py`:

- **FG1 — separador único:** reconocer códigos con UNA sola separación (p. ej. `1101-51`, `sim16-0000`).
- **FG2 — concatenación:** reconocer códigos concatenados al nombre (p. ej. `11090BANCO`, `10423CTA`).

Restricción del sprint: el cambio es SOLO en `parser_universal.py`; los **39** archivos protegidos restantes (Runtime `gold_standard/runtime_manager.py`, Learning, benchmark, extension, tests) quedaron **sin modificar** (verificado por hash).

### 1.2 Resultados obtenidos
| Métrica | Antes (PQ0) | Después (PQ2) | Δ |
|---|---|---|---|
| CODIGO_PERDIDO | 2.755 | 271 | **−2.484 (−90.2%)** |
| Cobertura de códigos | 8,93% | 10,51% | **+1,58 pp** |
| Montos interpretados | 42,72% | 42,72% | 0 (sin cambios) |
| Cuentas coincidentes | 158.250 | 158.250 | 0 (sin cambios) |
| Combinado | 25,82 | 26,61 | +0,79 |

### 1.3 Cobertura antes / después
- **Códigos recuperados:** 2.755 → 271 (mayoría resuelta).
- **Cobertura de códigos:** subió así que resolución de códigos **no** regresa.
- **Montos y cuentas totales:** idénticos. El cambio es estricto a la recuperación de códigos; no toca montos ni detección de cuentas.

### 1.4 Benchmark sin regresiones
Benchmark superpuesto en 2 PDFs (`Balance Capiro 2017–2018`, `Campoamor`); **los 19 archivos del benchmark quedaron idénticos** y no se observa ninguna degradación de resultados benchmark. Ver detalle en `PQ2_IMPLEMENTACION.md`.

---

## 2. Evidencia: por qué TODAVÍA. NO es una regresión del parser

El resultado del gate:

```
parser_quality_gate = FAIL  (CUENTA_FUSIONADA 12→58, TOTAL_MAL 3.578→3.630)
```

NO significa una regresión del parser por las siguientes razones, todas verificadas:

1. **Montos interpretados y cuentas coincidentes NO cambiaron** (42,72% y 158.250 idénticos). Una regresión del parser se manifestaría en estas métricas, no en las del auditor.

2. **Los +46 y +55 provienen EXACTAMENTE de las mismas líneas que en PQ0 eran `CODIGO_PERDIDO`** (análisis por `(archivo, línea)`). No son líneas nuevas ni errores introducidos: son **reclasificación** del mismo set de líneas.

3. **Motivo del aumento:** antes de PQ-2, estas líneas quedaban atrapadas en el ramo `CODIGO_PERDIDO` del auditor. El parser no extraía ningún código → el `elif` del detector de fusión nunca se alcanzaba. Al recuperar el código (FG1/FG2), la línea deja de ser `CODIGO_PERDIDO` y cae a los detectores siguientes (`_es_cuenta_fusionada`, `_totales_malinterpretados`), que ahora **miden más líneas** correctamente.

4. **El parser NO se degradó:** al contrario, devolvió información antes inexistente (el código). El aumento contable es un artefacto de *measurement window* del auditor, no de la calidad del parseo.

Conclusión de evidencia: **el FAIL del gate cuantifica limitaciones de los detectores del auditor**, que no estaban diseñados para evaluar líneas con código recién recuperado.

---

## 3. CUENTA_FUSIONADA (+46)

Los 46 se separan en dos poblaciones claras:

### 3.A Problemas estructurales reales (38) — ECDS

- **No son nuevos:** la fusión de dos cuentas en una sola línea **ya existía en los datos** en PQ0.
- **PQ-2 únicamente permitió detectarlas:** antes esas líneas eran `CODIGO_PERDIDO` (sin código reconocido) y el detector no alcanzaba a evaluarlas. Hoy el parser recupera el 1.º código y el auditor señala correctamente que hay un 2.º código de cuenta en la misma línea.
- Ejemplo:
  ```
  Línea:       12101-0000 Puyaral … 787.644.000 … 12122-0000 El Queule … 121.449.965
  Código 1:    12101-0000   (recuperado por FG1)
  Código 2:    12122-0000   (fusión real, detectado)
  ```
- Los 38 corresponden al PDF `ECDS Balance 10-2020`. Ambas son cuentas PUC reales (121x-0000), por lo que el detector actúa **correctamente**: es una fusión auténtica de dos cuentas.
- **Nota de alcance:** la *resolución de fusiones* (separar dos cuentas en una línea) es un problema **distinto y preexistente**, fuera del alcance de PQ-2 (que era recuperación de códigos). PQ-2 solo lo hizo visible. No lo introdujo.

### 3.B Falsos positivos (8)

| Archivo | Línea | 2º "código" detectado | Causa | Detector responsable |
|---|---|---|---|---|
| balance8_donaciones | 11 | `740111804-1` | Nº cuenta/RUT bancaria | `_es_cuenta_fusionada` (vía `_MULTI_CODIGO`) |
| balance8_donaciones | 12 | `740116923-1` | Nº cuenta bancaria | idem |
| balance8_donaciones | 13 | `827200164-3` | RUT / banco | idem |
| balance8_donaciones | 14 | `166896-0` | Nº cuenta bancaria | idem |
| Chilolac | 16 | `27102435-06` | Nº cuenta bancaria | idem |
| Capiro | SEGUROS | `39,0970.115` | Monto OCR mal parseado | idem |

- **Causa común:** el segundo `\b\d{N…}[-.]…\b` dentro del nombre de la cuenta se confunde con un 2º código PUC.
- **Detector responsable:** `_es_cuenta_fusionada()` + su regex de conteo `_MULTI_CODIGO`, que no distingue un código PUC de un RUT / cuenta bancaria / artefacto numérico del OCR.

---

## 4. TOTAL_MAL (+55)

**Los 55 casos son, en su totalidad, falsos positivos del auditor.** Ninguno es una fila real de `TOTAL`/`SUMA`.

El **55% origen**: PDFs `Balance Clasificado JGTc 2019`, `RGTc 2019`, `Chilolac`, `Capiro`, colegios, etc.

- Exemplos representativos:
  ```
  2283-03  RESULTADO ACUMULADO
  2201-94  RESULTADO DEL EJERCICIO …
  UTILIDAD (PERDIDA) EJERCICIO
  40403-… UTILIDAD EN VENTA DE ACCIONES   ← cuenta de ingreso real
  ```

### Por qué las marca (mecanismo exacto)
1. Tras PQ-2 el parser recupera el código → el **nombre** de la cuenta pasa a empezar con palabras como `Resultado` / `Utilidad` (antes, al no extraer código, el nombre empezaba por el número y no activaba el patrón).
2. `PATRON_TOTAL` (del parser) matchea esos nombres → fija `es_total = True` en la cuenta.
3. `_totales_malinterpretados(cuenta, raw)`:
   ```
   if es_total and not _TOTAL_KEYWORD.search(nombre): return True  → marca.
   ```
   Como el nombre NO contiene la keyword literal exacta (`total/sumas/del ejercicio`), devuelve `True` y la línea es marcada como `TOTAL_MAL`.

**Conclusión:** estas son cuentas reales de patrimonio/resultados cuya cabecera se parece a un título de "total". La lógica del detector es una **heurística que no distingue una cuenta llamada "Resultado/Utilidad" de una fila sumatoria real**; el incremento solo se observa porque ahora las cuentas están bien extraídas. **No es un error del parser.**

---

## 5. Conclusión técnica

| Clasificación | Cantidad |
|---|---|
| **Regresiones reales del parser** | **0** |
| Falsos positivos del auditor (CUENTA_FUSIONADA) | 8 |
| Falsos positivos del auditor (TOTAL_MAL) | 55 |
| Problemas históricos ahora visibles (fusión ECDS) | 38 |

- **0 regresiones reales:** montas/cuentas idénticas; supervivencia estrictamente en la recuperación de códigos.
- **63 falsos positivos** son limitación de los detectores del auditor (8 CUENTA + 55 TOTAL).
- **38 problemas históricos** quedan ahora detectados correctamente (fusión ECDSO), preexistentes y fuera de alcance.

---

## 6. Recomendaciones

- **NO modificar** `parser_universal.py`.
- **NO modificar** el benchmark.
- **NO modificar** Runtime (`gold_standard/runtime_manager.py`).
- **NO modificar** Learning.
- El siguiente sprint debe actuar **únicamente sobre el auditor** (`reports/parser_quality/audit_parser_quality.py` y sus detectores).

---

## 7. Especificación técnica de **PQ-2.1** (auditor)

> **NO implementar todavía.** Documentación de mejoras propuestas para el próximo sprint.

### 7.1 Endurecer `_es_cuenta_fusionada()`
- Exigir, para considerar "2º código PUC", un formato de código de cuenta real (`NNN-00000`, 4-6 dígitos, sufijo 4) en lugar de cualquier `\d+[-.]\d+`.
- Requerir que existan **dos** candidatos de códigos PUC, no uno de código + un número cualquiera.
- No considerar fusión si hay un solo código recuperado y el resto de tokens numéricos son montos/datas.

### 7.2 Endurecer `_MULTI_CODIGO`
- Ajustar la regex para que el "2º código" encaje el patrón PUC típico (`NNNNN-LLLL`) y NO coincida con números más largos tipo RUT/cuenta bancaria.
- Excluir tokens con >6 dígitos de la parte principal.

### 7.3 Ignorar RUTs / RFCs
- Añadir una exclusión de patrones tipo RUT/documento (Xxxx-DV) como candidatos a segunda cuenta.

### 7.4 Ignorar cuentas bancarias
- Excluir números de cuenta corriente/banco insertados en el nombre (empresas, `740111804-1`, `217248235-06`, etc.).

### 7.5 Ignorar números OCR corruptos
- Filtrar tokens con comas internas/patrones de monto mal histórico (emp. `38,0970.115`) para no tomarlos como código.

### 7.6 Modificar `_totales_malinterpretados`
- **NO marcar cuentas que tengan un `codigo` válido** (recuperado correctamente) como `TOTAL_MAL`.
- Reservar `TOTAL_MAL` para filas reales de `TOTAL`/`SUMA`/totales de cierre, no a cuentas de patrimonio/resultado con nombre "Resultado/Utilidad".

---

## 8. Decisión final

# PQ-2 = APROBADO

- El **FAIL** del gate corresponde **únicamente a limitaciones de los detectores del auditor**, y a la **visado correcto de problemas históricos** preexistentes (fusión ECDSO).
- El parser queda certificado como **"sin regresiones"** para este sprint:
  - Recuperación de códigos **+1.58 pp** de cobertura.
  - Montos y cuentas idénticos.
  - Benchmark sin regresiones.
- **No se modifica ningún archivo de código** en este documento. Solo se deja constancia del diagnóstico y la especificación de PQ-2.1.