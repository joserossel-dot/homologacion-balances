# Contrato Explícito de Confianza, Pisos de Regresión y Validación en Gold Schema 2

Fecha: 2026-10-05

Ámbito: Certificación de Corpus, Migración de Libros Gold y Paquetes de Revisión

Versión del Contrato: 1 (`Gold_confidence_contract_version = 1`)

---

## 1. Taxonomía y Distinción Documental

El sistema distingue formalmente cuatro conceptos independientes:

1. **Umbral de Cola de Revisión (`LOW_CONFIDENCE_THRESHOLD = 0.85`):**

   Definido en `review/review_metrics.py`. Criterio operacional de triaje que enruta cuentas a la cola de revisión humana prioritaria cuando la confianza cae por debajo de 0.85. No es un criterio de certificación contable.
2. **Confianza Observada del Motor (`Confianza_extraccion`):**

   Métrica empírica continua en $[0.0, 1.0]$ emitida por el parser/extractor. Refleja la calidad técnica del trazado (ej. `1.0` en texto digital limpio; `0.75` en reconstrucción tabular nativa degradada bajo `native_corrupt_coordinates` o `native_fragment_reconstruction`).
3. **Piso de Regresión Gold por Fila (`Confianza_minima`):**

   Piso documental mínimo tolerado para **esa fila contable específica** en la suite de certificación. No es un umbral global:
   - Una fila cuya confianza observada es `1.0` tiene piso `1.0` y **nunca se rebaja automáticamente a 0.75**. Una regresión futura a 0.75 fallará.
   - Una fila cuya confianza observada es `0.75` y fue revisada y aprobada humanamente fija su piso en `0.75`.
   - La migración solo adopta un piso inferior cuando existe `Estado_revision = APROBADO` y trazabilidad de revisión explícita.
4. **Validación Humana Obligatoria (`Estado_revision`):**

   Gobernanza humana explícita (`APROBADO`, `EXCLUIR`). La validación humana ya no se representa como el escalar numérico `1.0`. Cualquier estado `CORREGIR`, `PENDIENTE` o vacío bloquea inmediatamente la certificación con `ValueError`.

---

## 2. Marcador Explícito de Contrato y Reglas de Compatibilidad

Para evitar que la presencia accidental o malformada de columnas altere la semántica de certificación, se establece un marcador explícito:

- En archivos `.xlsx`, la hoja `Resumen` debe declarar la columna `Gold_confidence_contract_version = 1`.
- En archivos `.json`, el objeto raíz debe declarar `"Gold_confidence_contract_version": 1`.

### Matriz de Validación Fail-Closed

| Marcador en Resumen / JSON | Columna / Campo Confianza Mínima | Comportamiento |
| :--- | :--- | :--- |
| **Falta marcador** | **Falta columna** | **Modo Legado:** Igualdad estricta (`actual == expected`). Ningún libro legado se aprueba silenciosamente. |
| **Falta marcador** | **Existe columna** | **Bloqueo (ValueError):** Discrepancia estructural (columna de contrato sin marcador formal). |
| **Declara versión 1** | **Falta columna** | **Bloqueo (ValueError):** Marcador activo pero sin pisos declarados para filas aprobadas. |
| **Declara versión 1** | **Existe columna** | **Modo Contrato v1:** Comparación por piso de regresión por fila (`actual >= min_threshold`). |
| **Versión desconocida (!= 1)** | Indiferente | **Bloqueo (ValueError):** Versión de contrato no soportada. |

---

## 3. Validación de Valores Finitos y Rangos

Tanto la confianza observada (`actual_conf`) como el piso mínimo (`min_threshold`) deben ser números finitos validados con `math.isfinite`:
- Rango admisible: $[0.0, 1.0]$.
- Valores bloqueados explícitamente: `NaN`, `+inf`, `-inf`, valores negativos ($< 0.0$), valores mayores a 1 ($> 1.0$) y texto no numérico.
- En `load_gold_rows`: Valores no finitos o fuera de rango en libros aprobados disparan `ValueError`.
- En `evaluate_gold_rows`: Cualquier valor observado o piso no finito o fuera de rango genera discrepancia en `confidence` y bloquea la certificación.

---

## 4. Integridad Estructural y Hojas Obligatorias

En la carga y migración de libros Gold (`load_gold_rows` y `migrate_gold_workbook`):
- Se exige la existencia estricta de las hojas `Resumen` y `Cuentas`.
- La ausencia de cualquiera de ellas dispara un `ValueError` descriptivo antes de procesar datos.
- Se eliminan excepciones genéricas (`except Exception`), garantizando que cualquier falla de E/S o validación se propague inmediatamente, impidiendo la generación de libros parcialmente migrados.

---

## 5. Política de Clasificación Vinculada

De acuerdo con `docs/POLITICA_GLOBAL_CLASIFICACION_20260907.md`, la etiqueta `Otros pasivos financieros no corrientes` se encuentra formalmente aprobada como `PNC.05` bajo la regla canónica de `audited_statement_label`, quedando desvinculada de la heurística histórica `PNC.01`.

---

## 6. Vinculación Estricta al Hash Documental para Pisos de Confianza < 1.0

Para cualquier fila Gold aprobada con `Confianza_minima < 1.0` (específicamente el piso `0.75` autorizado exclusivamente para las 37 filas de DOC-01):
1. **Declaración en Gold:** La hoja `Resumen` del libro Gold debe declarar explícitamente el `SHA256` documental certificado.
2. **Declaración en Manifiesto:** El manifiesto de certificación debe declarar la expectativa `expect.sha256` idéntica.
3. **Validación Real de Entrada:** El documento procesado debe coincidir exactamente en su hash SHA-256 (64 caracteres hexadecimales).
4. **Comportamiento Fail-Closed:** Si falta el hash en el libro Gold, en el manifiesto o en el resultado procesado, o si se detecta cualquier discrepancia entre los tres hashes, la ejecución se bloquea inmediatamente con `ValueError`.
5. **No Extensión a Otros Documentos:** Un archivo con diferente contenido o hash nunca puede beneficiarse del piso 0.75.
6. **Igualdad Estricta en Pisos 1.0:** Los documentos DOC-02 y DOC-03 conservan piso 1.0 en todas sus filas y no son rebajados.

---

## 7. Preservación Atómica de Salidas Preexistentes ante Fallos

En `migrate_gold_workbook()`:
- No se elimina el archivo de salida previo antes de validar completamente las entradas.
- Se crea un archivo temporal único (`.{stem}.tmp_{uuid}.xlsx`) en el mismo directorio del destino.
- El archivo temporal se escribe y valida de forma íntegra (`validate_workbook_resumen_and_cuentas`).
- El reemplazo del archivo de salida se efectúa únicamente al completar exitosamente toda la validación mediante reemplazo atómico (`os.replace`).
- Si ocurre cualquier error, se captura la excepción, se elimina exclusivamente el archivo temporal (`temp_output.unlink()`) y se preserva íntegramente el archivo de salida preexistente con su SHA-256 anterior intacto.
