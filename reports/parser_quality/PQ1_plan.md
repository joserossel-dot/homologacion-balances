# PQ-1 — Parser Quality Sprint 1 (Plan)

**Estado:** Borrador para planificación
**Autor:** Sprint PQ (infraestructura de medición)
**Depende de:** Parser Quality Program (auditoría `reports/parser_quality/audit_parser_quality.py`)

---

## 1. Objetivos

1. **Medir** la calidad real del parser de producción sobre los 608 PDFs del corpus
   (holguras: ninguna — el sprint previo ya definió las métricas por documento).
2. **Priorizar** con datos (Pareto) los problemas del parser: identificar el
   conjunto mínimo de problemas que explica ≥95% de los errores.
3. **Blindar** el benchmark congelado M5 (2660/2662): ninguna mejora puede romperlo.
4. **Establecer** un ciclo reproducible de mejora: auditoría → hipótesis →
   implementación → re-auditoría → comparación → aceptar/revertir.
5. **Automatizar** la verificación de regresiones con el Quality Gate (`PASS`/`FAIL`).

## 2. Alcance

### Incluye
- Auditoría de calidad sobre **todo** el corpus (608 PDFs).
- Herramientas de medición y comparación:
  - `tools/parser_quality_compare.py` — diff entre ejecuciones.
  - `tools/parser_quality_gate.py` — quality gate (regresiones).
  - `reports/parser_quality/parser_quality_diff.md` — salida del diff.
- Documentación: este plan + `PARSER_IMPROVEMENT_GUIDE.md`.
- Detección automática de 8 tipos de problema por documento.

### Excluye (prohibido tocar)
- `parser_universal.py`
- Cualquier extractor (`document_intelligence/extractors/*`)
- `learning/` (engine y perfiles)
- Runtime (`gold_standard/runtime_manager.py`, pipeline de producción)
- Benchmark M5 congelado y su manifest (`benchmark/dataset_manifest.csv`)
- El conjunto gold estándar

> Regla: en este sprint **solo se mide y se audita**. Toda corrección es objeto
> de un sprint posterior que deba pasar el gate.

## 3. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Auditoría lenta (OCR) | Extensión del sprint | Checkpoint cada 25 PDFs + `--resume` |
| Falsos positivos en detectores | Ruido en el Pareto | Revisión manual de una muestra por detector |
| Regresión silenciosa al corregir | Calidad cae | Quality Gate con baseline fijo |
| Benchmark congelado roto por cambio | Certificación inválida | Gate verifica dominio + hash del benchmark |
| Dataset/auditoría con `path` inconsistentes | Diff sesgado | Normalizar por `archivo` (nombre de fichero) |
| PDFs con texto nativo vacío | OCR lento y con ruido | Registrar `ocr_o_texto=OCR`, tiempo separado |

## 4. Criterios de éxito

1. Auditoría completa de 608 PDFs con checkpointing y resume funcional.
2. Los 4 reportes generados (`report.md`, `dataset.csv`, `findings.csv`, `pareto.md`).
3. Diff de auditoría producido (`parser_quality_diff.md`) comparando baseline vs current.
4. Quality Gate con `PASS`/`FAIL` reproducible sobre fixtures y sobre datos reales.
5. Top-10 problemas que expliquen ≥95% de los hallazgos identificado en el Pareto.
6. **Confirmación explícita**: el parser no fue modificado durante el sprint
   (verificación por hash de los ficheros protegidos).

## 5. Archivos involucrados

### Nuevos (este sprint)
- `reports/parser_quality/PQ1_plan.md` — este documento
- `reports/parser_quality/PARSER_IMPROVEMENT_GUIDE.md` — guía de mejora
- `tools/parser_quality_common.py` — carga de CSVs y métricas compartidas
- `tools/parser_quality_compare.py` — comparación entre ejecuciones
- `tools/parser_quality_gate.py` — quality gate
- Tests: `tests/test_parser_quality_tools.py`

### Producto de la auditoría (preexistente del PQ previo)
- `reports/parser_quality/audit_parser_quality.py`
- `reports/parser_quality/parser_quality_dataset.csv`
- `reports/parser_quality/parser_quality_findings.csv`
- `reports/parser_quality/parser_quality_report.md`
- `reports/parser_quality/parser_quality_pareto.md`
- `reports/parser_quality/_parser_quality_checkpoint.json` (temporal, resume)

### Prohibidos de modificar
- `parser_universal.py`, `document_intelligence/extractors/*`, `learning/*`,
  `gold_standard/runtime_manager.py`, `benchmark/*`, gold estándar.

## 6. Estrategia de pruebas

### Unitarias (herramientas)
- `tests/test_parser_quality_tools.py` con **fixtures sintéticos**:
  - carga de dataset/findings
  - cálculo de cobertura y tiempos
  - diff: tipos, PDFs mejorados/empeorados, Pareto, tiempos
  - gate: caso PASS y caso FAIL (cada condición por separado)

### Integración (con datos reales)
1. Ejecutar auditoría completa (608) con `--resume`.
2. Congelar snapshot baseline (copiar `reports/parser_quality` a un directorio `baseline/`).
3. Ejecutar el gate: `--baseline baseline --current reports/parser_quality` → esperar `PASS`.
4. Simular una regresión y verificar que el gate detecta `FAIL` en la condición exacta.
5. Verificar que el benchmark M5 (2660/2662) se mantiene.

### Criterios de aceptación de un cambio de parser (sprint futuro)
- Gate `PASS` frente al baseline.
- Cobertura igual o mayor.
- Ningún tipo de error aumenta.
- Benchmark congelado sin cambios.

## 7. Estrategia de rollback

1. **Inmutabilidad del baseline**: el snapshot baseline se congela y se guarda
   aparte (`reports/parser_quality/_baseline/`); no se sobreescribe.
2. **Por feature**: cada mejora del parser se implementa en un branch con su
   propio diff de auditoría.
3. **Criterio de reversión**: si el gate devuelve `FAIL` (o el diff muestra
   regresión en cualquier tipo/PDF), se revierte el cambio y se re-ejecuta la
   auditoría hasta volver a `PASS`.
4. **Comparación**: `tools/parser_quality_compare.py` confirma que el estado
   post-rollback es idéntico (o mejor) que el baseline.
5. **Ficheros protegidos**: antes/después se verifica el hash de
   `parser_universal.py`, extractores, `learning/` y runtime para probar que no
   hubo modificaciones colaterales.

---

## Anexo — Estado del pipeline de medición

- Auditoría completa: **en curso** (checkpoint cada 25 PDFs, resume activo).
- Corpus objetivo: 608 PDFs.
