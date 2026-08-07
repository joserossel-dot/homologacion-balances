# PARSER_IMPROVEMENT_GUIDE.md

Guía para atacar un problema del parser de forma controlada y medible.

Sigue un ciclo estricto: de cada problema sale una **hipótesis**, una
**implementación**, una **medición** y una **decisión** (aceptar/revertir).
Nunca se toca el parser sin pasar por el ciclo completo.

```
Problema
   ↓
Hipótesis
   ↓
Implementación
   ↓
Re-ejecución auditoría
   ↓
Comparación
   ↓
Aceptar / Revertir
```

---

## 1. Problema

Identificar el problema **con datos**, no por intuición.

1. Usa el Pareto del Parser Quality Program
   (`reports/parser_quality/parser_quality_pareto.md`) para ver qué tipo de
   error domina. Ataca primero los tipos que más aportan al 95% acumulado.
2. Filtra los ejemplos concretos en `parser_quality_findings.csv`
   (archivo, línea, código, nombre en crudo).
3. Redacta el problema de forma medible:
   - **Qué se espera** (ej: `11010 CAJAS` → código `11010`, nombre `CAJAS`).
   - **Qué ocurre** (ej: cuenta `CAJAS` sin código; línea con `$` residual).
   - **Impacto medible** (ej: N documentos afectados, N cuentas con `cuentas_sin_codigo`).

> Criterio de entrada: el problema debe tener **al menos un detector automático**
> que lo cuente. Si no existe, añadir el detector ANTES de tocar el parser.

## 2. Hipótesis

Formular por qué ocurre el problema en el código del parser.

- No corrija a ciegas: diga qué condición del parser falla
  (ej: `PATRON_COMPACTO` no cubre `\d{5}`, la detección de columnas no divide,
  el filtro descarta la línea, etc.).
- Defina una **predicción verificable**: *"si ajusto X, el tipo `MONTO_PARTIDO`
  baja en los archivos Y, y el benchmark M5 no cambia"*.
- Elección de implementación: siempre que sea posible reutilizar infraestructura
  existente (extractors, `parser_universal`), NO inventar código nuevo al margen.

## 3. Implementación

- Trabajar en un **branch** separado para poder revertir.
- Cambios mínimos, anotados con:
  - qué archivo, qué función
  - el impacto esperado (cuentas, códigos, tiempos)
- **No mezclar** varias hipótesis en un mismo cambio: si dos causas, dos commits `=>
  dos mediciones`.
- No tocar los ficheros protegidos salvo que la hipótesis lo justifique y quede
  registrado en el diff del plan PQ.

## 4. Re-ejecución auditoría

1. Ejecutar la auditoría completa sobre el corpus:
   `python3 reports/parser_quality/audit_parser_quality.py --resume`
   (el checkpoint permite reanudar tras interrupciones).
2. Congelar un **snapshot baseline** antes de implementar (copiar
   `reports/parser_quality` → `reports/parser_quality/_baseline/`).
3. Tras el cambio, guardar el resultado como **current**.

> La auditoría debe correr sobre el MISMO corpus en baseline y current para que
> la comparación tenga sentido.

## 5. Comparación

Ejecutar:
```bash
python3 tools/parser_quality_compare.py \
    --baseline reports/parser_quality/_baseline \
    --current  reports/parser_quality \
    -o reports/parser_quality/parser_quality_diff.md
```
Revisar el diff:
- **Por tipo de error**: ¿aumenta alguno?
- **Por PDF**: lista de mejores y empeorados.
- **Cobertura acumulada (Pareto)**: ¿el 95% se alcanza con MENOS problemas?
- **Tiempo promedio / total**.

Y correr el gate:
```bash
python3 tools/parser_quality_gate.py \
    --baseline reports/parser_quality/_baseline \
    --current  reports/parser_quality
```
Debe devolver **PASS**. Si devuelve **FAIL**, la salida indica exactamente la
condición rota (tipo que subió, cobertura que bajó, PDF crítico nuevo,
benchmark modificado, o regresión nueva).

## 6. Aceptar / Revertir

- **ACEPTAR** si: el gate es `PASS` **y** el diff muestra mejora neta
  (menos hallazgos totales, cobertura ≥, y ninguna variable agravada).
- **REVERTIR** si el gate es `FAIL` o el diff muestra regresión. Revertir el
  branch del paso 3 → 1. Re-ejecutar la auditoría → 2. Confirmar que baseline
  == current (diff sin cambios) y que la hash de los ficheros protegidos no
  cambió.

---

## Checklist de un sprint de mejora

- [ ] Problema definido con métrica y ejemplos (findings.csv).
- [ ] Hipótesis con predicción medible.
- [ ] Cambio en branch separado, mínimo.
- [ ] Baseline congelado ANTES del cambio.
- [ ] Re-auditoría completa con `--resume`.
- [ ] `compare` genera `parser_quality_diff.md`.
- [ ] `gate` devuelve `PASS` (o se revierte).
- [ ] Benchmark M5 intacto; hash de ficheros protegidos sin cambios.
- [ ] Decisión documentada: aceptar/revertir + motivo.