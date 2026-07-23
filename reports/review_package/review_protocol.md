# Protocolo de Revisión — Gold Standard de Balances Tributarios

## Propósito

Generar un conjunto de datos gold standard (verdad absoluta) para validar y
mejorar el pipeline de homologación de balances tributarios chilenos.

Este conjunto servirá exclusivamente como **benchmark de evaluación**.
No se usará para entrenar, ajustar ni modificar reglas, diccionario, variantes
ni el catálogo CMCC.

## Estructura de la Muestra

| Dimensión | Cobertura |
|-----------|-----------|
| Documentos | 34 |
| Cuentas a revisar | ~2.200 |
| Layouts distintos | 28 de 28 (100%) |
| OCR | 17 documentos (50%) |
| Texto nativo | 17 documentos (50%) |
| Empresas distintas | 26 |

## Archivos del Paquete

| Archivo | Contenido |
|---------|-----------|
| `review_package.xlsx` | Documentos y cuentas a revisar (2 hojas) |
| `gold_standard_template.xlsx` | Template para completar (solo hoja de cuentas) |
| `review_protocol.md` | Este documento |

## Columnas del Template

### Hoja "Documentos" (solo informativa)

| Columna | Descripción |
|---------|-------------|
| `source_file` | Nombre del archivo original en `datasets/` |
| `group` | Grupo del dataset: `validacion` o `edge_cases` |
| `layout` | Firma del layout de columnas detectado |
| `requirio_ocr` | `SÍ` si el documento fue procesado con OCR |
| `company` | Nombre inferido de la empresa |
| `total_accounts` | Total de cuentas extraídas por el parser |

### Hoja "Cuentas" — a completar

| Columna | Descripción | Estado |
|---------|-------------|--------|
| `source_file` | Archivo de origen | ✅ Prellenado |
| `group` | Grupo del dataset | ✅ Prellenado |
| `line_number` | Número de línea o código en el balance original | ✅ Prellenado |
| `account_code` | Código de cuenta (si existe en el balance) | ✅ Prellenado |
| `account_name` | Nombre de la cuenta extraído por el parser | ✅ Prellenado |
| `nature` | Naturaleza contable: `profit` o `equity` | ✅ Prellenado |
| `classification_amount` | Monto asociado | ✅ Prellenado |
| `parser_standard_code` | Código CMCC asignado por el parser | ✅ Prellenado |
| `parser_final_code` | Código final asignado por el pipeline | ✅ Prellenado |
| `parser_method` | Método usado: `learning_exact`, `learning_fuzzy`, `dictionary_exact`, `dictionary_fuzzy`, `code`, `unclassified` | ✅ Prellenado |
| `parser_confidence` | Confianza del parser (0–1) | ✅ Prellenado |
| `parser_reason` | Razón textual de la decisión del parser | ✅ Prellenado |
| `gold_standard_code` | **Código CMCC correcto según su juicio** | ⬜ Completar |
| `gold_standard_name` | **Nombre estándar de la cuenta** | ⬜ Completar |
| `notes` | **Observaciones (discrepancias, dudas, casos especiales)** | ⬜ Completar |

## Cómo Completar

### Paso 1: Abrir el archivo del balance

Cada `source_file` en el template corresponde a un PDF en `datasets/edge_cases/`
o `datasets/validacion/`. Abra el PDF para ver el balance original.

### Paso 2: Revisar cada cuenta

Para cada fila en la hoja "Cuentas":

1. **Ubique la cuenta** en el PDF original usando `account_code` y `account_name`.
2. **Determine el código CMCC correcto** según el catálogo maestro (ver sección
   "Códigos CMCC" más abajo).
3. **Si el parser ya asignó un código y es correcto**, cópielo en
   `gold_standard_code`.
4. **Si el parser asignó un código incorrecto o no asignó ninguno**,
   ingrese el código correcto.
5. **Si no puede determinar el código** (cuenta ambigua, ilegible, etc.),
   deje `gold_standard_code` vacío y explique en `notes`.

### Paso 3: Códigos CMCC

El catálogo maestro (`CMCC`) usa esta estructura de códigos:

| Prefijo | Categoría | Ejemplo |
|---------|-----------|---------|
| `AC.` | Activo Corriente | `AC.01` Caja y Bancos |
| `ANC.` | Activo No Corriente | `ANC.03` Propiedades, Planta y Equipo |
| `PC.` | Pasivo Corriente | `PC.01` Proveedores |
| `PNC.` / `PAS.` | Pasivo No Corriente | `PNC.02` Obligaciones Bancarias LP |
| `PAT.` | Patrimonio | `PAT.01` Capital |
| `ER.` | Estado de Resultados | `ER.04` Gastos de Administración |

El catálogo completo está disponible en `catalogo_maestro.json`.

### Paso 4: Criterios para códigos

| Situación | Acción |
|-----------|--------|
| Cuenta claramente identificable | Asignar código CMCC exacto |
| Cuenta del tipo "Varios" o "Otras" | Usar código genérico de la categoría (ej. `ER.99` Otros Gastos) |
| Cuenta con múltiples conceptos combinados | Usar el código del concepto principal o el de mayor monto |
| Total / Subtotal | Dejar vacío, marcar en `notes` como "total" |
| Encabezado / Fecha / RUT / Notas | Dejar vacío, marcar en `notes` como "no es cuenta" |
| Texto ilegible o ruido OCR | Dejar vacío, marcar en `notes` como "ilegible" |

### Paso 5: Observaciones en `notes`

Use `notes` para documentar:

- Cuentas que el parser clasificó incorrectamente
- Cuentas que no pudo clasificar
- Discrepancias entre el balance y el estándar
- Casos donde el nombre de cuenta no coincide con su naturaleza
- Cualquier ambigüedad o duda

## Reglas de Decisión

### Cuentas con código en el balance original

Si el balance original incluye códigos contables (numeración SII estándar):

1. Busque el código en `catalogo_maestro.json` o en la tabla de referencia
2. Si el código existe, asigne el concepto CMCC correspondiente
3. Si el código no existe en el catálogo, determine el concepto por el nombre

### Cuentas sin código (solo nombre)

1. Busque coincidencia exacta en `diccionario.json`
2. Si no hay coincidencia, use su juicio contable para asignar el código
3. Documente la decisión en `notes`

### Layouts con Deudor/Acreedor

Para balances en formato Deudor/Acreedor (6 columnas):

- Las cuentas deudoras suelen ser Activos o Gastos
- Las cuentas acreedoras suelen ser Pasivos, Patrimonio o Ingresos
- Use la columna de origen como señal, pero verifique el nombre

### Layouts con Activo/Pasivo/Pérdida/Ganancia

Para balances en formato de 4 columnas:

- Columna Activo → Activos (AC o ANC)
- Columna Pasivo → Pasivos (PC, PNC, o PAT)
- Columna Pérdida → Gastos o Pérdidas (ER)
- Columna Ganancia → Ingresos o Ganancias (ER)

### Documentos OCR

Si el documento requirió OCR:

- Verifique que el texto extraído coincida con el PDF escaneado
- Si hay errores de OCR obvios, anote la corrección en `notes`
- Si no puede leer el original, deje `gold_standard_code` vacío

## Formato de Entrega

1. Complete el archivo `gold_standard_template.xlsx`
2. Solo debe modificar las columnas `gold_standard_code`, `gold_standard_name`
   y `notes`
3. No elimine ni reordene filas
4. Guarde con el nombre `gold_standard_completed.xlsx`

## Checklist Final

Antes de entregar, verifique:

- [ ] Todas las cuentas claras tienen `gold_standard_code` asignado
- [ ] Las cuentas ambiguas tienen `notes` explicando la duda
- [ ] No se modificaron columnas prellenadas
- [ ] No se eliminaron filas

---

**Proyecto:** Homologación de Balances Tributarios
**Versión del protocolo:** 1.0
**Fecha de generación:** Julio 2026
