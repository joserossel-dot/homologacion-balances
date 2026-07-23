# Auditoría del Sistema de Diccionarios

Generado: 2026-07-07 16:38:06

---

## 1. Resumen Ejecutivo

| Métrica | diccionario.json | diccionario_actualizado.json | diccionario_optimizado.json |
|---------|-----------------:|----------------------------:|--------------------------:|
| Entradas | 826 | 781 | 712 |
| Nombres únicos | 826 | 781 | 712 |
| Códigos únicos | 49 | 49 | 46 |
| Fuentes únicas | 9 | 8 | 6 |
| Nombres duplicados | 0 | 0 | 0 |
| Entradas vacías | 0 | 0 | 0 |
| Nombres sospechosos | 16 | 16 | 12 |
| Códigos inválidos | 0 | 0 | 0 |

## 2. Comparación Cruzada

- **Comunes a los 3 archivos:** 712
- **Solo en diccionario.json:** 45
- **Solo en diccionario_actualizado.json:** 0
- **Solo en diccionario_optimizado.json:** 0
- **Mismo nombre, distinto código:** 0

## 3. diccionario.json

- **Total entradas:** 826
- **Nombres únicos:** 826
- **Códigos únicos:** 49

### Códigos con múltiples nombres

- `AC.01` → 28 nombres distintos
- `AC.02` → 10 nombres distintos
- `AC.03` → 25 nombres distintos
- `AC.04` → 11 nombres distintos
- `AC.05` → 33 nombres distintos
- `AC.06` → 15 nombres distintos
- `AC.06S` → 16 nombres distintos
- `AC.07` → 53 nombres distintos
- `AC.08` → 7 nombres distintos
- `AC.09` → 6 nombres distintos
- `ANC.01` → 62 nombres distintos
- `ANC.03` → 12 nombres distintos
- `ANC.04` → 6 nombres distintos
- `ANC.05` → 9 nombres distintos
- `ANC.06` → 24 nombres distintos
- `ANC.07` → 9 nombres distintos
- `ANC.08` → 5 nombres distintos
- `ER.01` → 15 nombres distintos
- `ER.02` → 45 nombres distintos
- `ER.04` → 90 nombres distintos
- `ER.05` → 5 nombres distintos
- `ER.07` → 5 nombres distintos
- `ER.09` → 25 nombres distintos
- `ER.10` → 3 nombres distintos
- `ER.12` → 8 nombres distintos
- `ER.13` → 21 nombres distintos
- `ER.14` → 14 nombres distintos
- `ER.15` → 9 nombres distintos
- `ER.16` → 8 nombres distintos
- `PAT.01` → 9 nombres distintos
- `PAT.02` → 16 nombres distintos
- `PAT.03` → 11 nombres distintos
- `PAT.04` → 5 nombres distintos
- `PAT.05` → 5 nombres distintos
- `PC.01` → 11 nombres distintos
- `PC.02` → 28 nombres distintos
- `PC.03` → 4 nombres distintos
- `PC.04` → 8 nombres distintos
- `PC.05` → 35 nombres distintos
- `PC.06` → 38 nombres distintos
- `PC.07` → 7 nombres distintos
- `PC.08` → 35 nombres distintos
- `PNC.01` → 13 nombres distintos
- `PNC.02` → 2 nombres distintos
- `PNC.04` → 4 nombres distintos
- `PNC.05` → 11 nombres distintos

### Nombres sospechosos

- `Banco Bci $ Egresos DSI` → caracteres_extraños
- `Banco Santander $` → caracteres_extraños
- `Impuesto de 2° Categoría por Pagar` → caracteres_extraños
- `BANCO DE CHILE N°` → caracteres_extraños
- `BCI N°` → caracteres_extraños
- `Crédito BCI N° 902445` → caracteres_extraños
- `Proveedores Extranjeros US$` → caracteres_extraños
- `I+D` → caracteres_extraños
- `> < valor de inversiones` → caracteres_extraños
- `ctas por cobrar leasing 3° LP` → caracteres_extraños
- `credito impto 2° categoria` → caracteres_extraños
- `crédito impuesto 2° categoría` → caracteres_extraños
- `— 1,2.08,01 Nogales` → caracteres_extraños
- `Impuesto retención 2* Categ` → caracteres_extraños
- `Intereses Créditos Bancarios 54,399,278 10] 54,399,278 0 : 0 o 54,399,278 [0]` → caracteres_extraños
- `BANCO CREDITO E INVERSIONES N°` → caracteres_extraños

### Posibles duplicados (normalización)

- Normalizado: `CLIENTES VENTAS A CREDITO` → ['Clientes Ventas a Credito', 'Clientes Ventas a Crédito']
- Normalizado: `IMPORTACIONES EN TRANSITO` → ['Importaciones en Tránsito', 'importaciones en transito']
- Normalizado: `IVA CREDITO FISCAL` → ['IVA CREDITO FISCAL', 'iva Crédito Fiscal']
- Normalizado: `REVALORIZACION CAPITAL PROPIO` → ['REVALORIZACION CAPITAL PROPIO', 'Revalorización Capital Propio']
- Normalizado: `DEPRECIACION ACTIVOS EN LEASING` → ['Depreciación Activos en Leasing', 'DEPRECIACÍON ACTIVOS EN LEASING']
- Normalizado: `LINEA DE CREDITO BANCO INTERNACIONAL` → ['Línea de Crédito Banco Internacional', 'LINEA DE CRÉDITO BANCO INTERNACIONAL']
- Normalizado: `PROVISION DOCUMENTOS POR RECIBIR` → ['Provisión Documentos por Recibir', 'PROVISION DOCUMENTOS POR RECIBIR']
- Normalizado: `CORRECCION MONETARIA` → ['Corrección Monetaria', 'Correccion monetaria']
- Normalizado: `DEPRECIACION ACUMULADA` → ['DEPRECIACION ACUMULADA', 'DEPRECIACIÓN ACUMULADA']
- Normalizado: `ACTIVOS BIOLOGICOS CORRIENTES` → ['activos biologicos corrientes', 'Activos biológicos corrientes']
- Normalizado: `ASIGNACION FAMILIAR` → ['asignacion familiar', 'asignación familiar']
- Normalizado: `CARTAS DE CREDITO IMPORTACION` → ['cartas de credito importacion', 'cartas de crédito importación']
- Normalizado: `LETRAS EN GARANTIA` → ['letras en garantia', 'letras en garantía']
- Normalizado: `MAYOR VALOR POR RETASACION` → ['mayor valor por retasacion', 'mayor valor por retasación']
- Normalizado: `PARTICIPACION DEVENGADA` → ['participacion devengada', 'participación devengada']
- Normalizado: `CREDITOS A IMPORTACION` → ['creditos a importacion', 'créditos a importación']
- Normalizado: `INSTITUCIONES DE PREVISION` → ['instituciones de prevision', 'instituciones de previsión']
- Normalizado: `PROVISION GASTOS` → ['provision gastos', 'provisión gastos']
- Normalizado: `INDEMNIZACION ANOS DE SERVICIOS` → ['indemnizacion años de servicios', 'indemnización años de servicios']
- Normalizado: `GARANTIAS DE ARRIENDOS RECIBIDAS` → ['garantias de arriendos recibidas', 'garantías de arriendos recibidas']
- Normalizado: `INTERES MINORITARIO` → ['Interes minoritario', 'interés minoritario']
- Normalizado: `RESERVA DE REVALORIZACION` → ['reserva de revalorizacion', 'reserva de revalorización']
- Normalizado: `(-) PERDIDAS ACUMULADAS` → ['(-) perdidas acumuladas', '(-) pérdidas acumuladas']
- Normalizado: `UTILIDADES HISTORICAS` → ['utilidades historicas', 'utilidades históricas']
- Normalizado: `PLUSVALIA` → ['Plusvalía', 'Plusvalia']

## 3. diccionario_actualizado.json

- **Total entradas:** 781
- **Nombres únicos:** 781
- **Códigos únicos:** 49

### Códigos con múltiples nombres

- `AC.01` → 25 nombres distintos
- `AC.02` → 10 nombres distintos
- `AC.03` → 25 nombres distintos
- `AC.04` → 11 nombres distintos
- `AC.05` → 32 nombres distintos
- `AC.06` → 15 nombres distintos
- `AC.06S` → 16 nombres distintos
- `AC.07` → 53 nombres distintos
- `AC.08` → 7 nombres distintos
- `AC.09` → 6 nombres distintos
- `ANC.01` → 62 nombres distintos
- `ANC.03` → 12 nombres distintos
- `ANC.04` → 6 nombres distintos
- `ANC.05` → 8 nombres distintos
- `ANC.06` → 24 nombres distintos
- `ANC.07` → 9 nombres distintos
- `ANC.08` → 5 nombres distintos
- `ER.01` → 15 nombres distintos
- `ER.02` → 36 nombres distintos
- `ER.04` → 68 nombres distintos
- `ER.05` → 5 nombres distintos
- `ER.07` → 5 nombres distintos
- `ER.09` → 21 nombres distintos
- `ER.10` → 3 nombres distintos
- `ER.12` → 8 nombres distintos
- `ER.13` → 19 nombres distintos
- `ER.14` → 14 nombres distintos
- `ER.15` → 9 nombres distintos
- `ER.16` → 8 nombres distintos
- `PAT.01` → 9 nombres distintos
- `PAT.02` → 16 nombres distintos
- `PAT.03` → 10 nombres distintos
- `PAT.04` → 5 nombres distintos
- `PAT.05` → 5 nombres distintos
- `PC.01` → 11 nombres distintos
- `PC.02` → 28 nombres distintos
- `PC.03` → 4 nombres distintos
- `PC.04` → 8 nombres distintos
- `PC.05` → 35 nombres distintos
- `PC.06` → 38 nombres distintos
- `PC.07` → 6 nombres distintos
- `PC.08` → 35 nombres distintos
- `PNC.01` → 12 nombres distintos
- `PNC.02` → 2 nombres distintos
- `PNC.04` → 4 nombres distintos
- `PNC.05` → 11 nombres distintos

### Nombres sospechosos

- `Banco Bci $ Egresos DSI` → caracteres_extraños
- `Banco Santander $` → caracteres_extraños
- `Impuesto de 2° Categoría por Pagar` → caracteres_extraños
- `BANCO DE CHILE N°` → caracteres_extraños
- `BCI N°` → caracteres_extraños
- `Crédito BCI N° 902445` → caracteres_extraños
- `Proveedores Extranjeros US$` → caracteres_extraños
- `I+D` → caracteres_extraños
- `> < valor de inversiones` → caracteres_extraños
- `ctas por cobrar leasing 3° LP` → caracteres_extraños
- `credito impto 2° categoria` → caracteres_extraños
- `crédito impuesto 2° categoría` → caracteres_extraños
- `— 1,2.08,01 Nogales` → caracteres_extraños
- `Impuesto retención 2* Categ` → caracteres_extraños
- `Intereses Créditos Bancarios 54,399,278 10] 54,399,278 0 : 0 o 54,399,278 [0]` → caracteres_extraños
- `BANCO CREDITO E INVERSIONES N°` → caracteres_extraños

### Posibles duplicados (normalización)

- Normalizado: `CLIENTES VENTAS A CREDITO` → ['Clientes Ventas a Credito', 'Clientes Ventas a Crédito']
- Normalizado: `IMPORTACIONES EN TRANSITO` → ['Importaciones en Tránsito', 'importaciones en transito']
- Normalizado: `IVA CREDITO FISCAL` → ['IVA CREDITO FISCAL', 'iva Crédito Fiscal']
- Normalizado: `REVALORIZACION CAPITAL PROPIO` → ['REVALORIZACION CAPITAL PROPIO', 'Revalorización Capital Propio']
- Normalizado: `DEPRECIACION ACTIVOS EN LEASING` → ['Depreciación Activos en Leasing', 'DEPRECIACÍON ACTIVOS EN LEASING']
- Normalizado: `LINEA DE CREDITO BANCO INTERNACIONAL` → ['Línea de Crédito Banco Internacional', 'LINEA DE CRÉDITO BANCO INTERNACIONAL']
- Normalizado: `PROVISION DOCUMENTOS POR RECIBIR` → ['Provisión Documentos por Recibir', 'PROVISION DOCUMENTOS POR RECIBIR']
- Normalizado: `CORRECCION MONETARIA` → ['Corrección Monetaria', 'Correccion monetaria']
- Normalizado: `DEPRECIACION ACUMULADA` → ['DEPRECIACION ACUMULADA', 'DEPRECIACIÓN ACUMULADA']
- Normalizado: `ACTIVOS BIOLOGICOS CORRIENTES` → ['activos biologicos corrientes', 'Activos biológicos corrientes']
- Normalizado: `ASIGNACION FAMILIAR` → ['asignacion familiar', 'asignación familiar']
- Normalizado: `CARTAS DE CREDITO IMPORTACION` → ['cartas de credito importacion', 'cartas de crédito importación']
- Normalizado: `LETRAS EN GARANTIA` → ['letras en garantia', 'letras en garantía']
- Normalizado: `MAYOR VALOR POR RETASACION` → ['mayor valor por retasacion', 'mayor valor por retasación']
- Normalizado: `PARTICIPACION DEVENGADA` → ['participacion devengada', 'participación devengada']
- Normalizado: `CREDITOS A IMPORTACION` → ['creditos a importacion', 'créditos a importación']
- Normalizado: `INSTITUCIONES DE PREVISION` → ['instituciones de prevision', 'instituciones de previsión']
- Normalizado: `PROVISION GASTOS` → ['provision gastos', 'provisión gastos']
- Normalizado: `INDEMNIZACION ANOS DE SERVICIOS` → ['indemnizacion años de servicios', 'indemnización años de servicios']
- Normalizado: `GARANTIAS DE ARRIENDOS RECIBIDAS` → ['garantias de arriendos recibidas', 'garantías de arriendos recibidas']
- Normalizado: `INTERES MINORITARIO` → ['Interes minoritario', 'interés minoritario']
- Normalizado: `RESERVA DE REVALORIZACION` → ['reserva de revalorizacion', 'reserva de revalorización']
- Normalizado: `(-) PERDIDAS ACUMULADAS` → ['(-) perdidas acumuladas', '(-) pérdidas acumuladas']
- Normalizado: `UTILIDADES HISTORICAS` → ['utilidades historicas', 'utilidades históricas']
- Normalizado: `PLUSVALIA` → ['Plusvalía', 'Plusvalia']

## 3. diccionario_optimizado.json

- **Total entradas:** 712
- **Nombres únicos:** 712
- **Códigos únicos:** 46

### Códigos con múltiples nombres

- `AC.01` → 18 nombres distintos
- `AC.02` → 10 nombres distintos
- `AC.03` → 20 nombres distintos
- `AC.04` → 8 nombres distintos
- `AC.05` → 26 nombres distintos
- `AC.06` → 14 nombres distintos
- `AC.06S` → 16 nombres distintos
- `AC.07` → 51 nombres distintos
- `AC.09` → 6 nombres distintos
- `ANC.01` → 53 nombres distintos
- `ANC.03` → 12 nombres distintos
- `ANC.04` → 6 nombres distintos
- `ANC.05` → 7 nombres distintos
- `ANC.06` → 23 nombres distintos
- `ANC.07` → 7 nombres distintos
- `ANC.08` → 5 nombres distintos
- `ER.01` → 15 nombres distintos
- `ER.02` → 34 nombres distintos
- `ER.04` → 68 nombres distintos
- `ER.05` → 5 nombres distintos
- `ER.07` → 4 nombres distintos
- `ER.09` → 21 nombres distintos
- `ER.10` → 3 nombres distintos
- `ER.12` → 8 nombres distintos
- `ER.13` → 19 nombres distintos
- `ER.14` → 13 nombres distintos
- `ER.15` → 9 nombres distintos
- `ER.16` → 8 nombres distintos
- `PAT.01` → 9 nombres distintos
- `PAT.02` → 16 nombres distintos
- `PAT.03` → 10 nombres distintos
- `PAT.04` → 5 nombres distintos
- `PAT.05` → 5 nombres distintos
- `PC.01` → 9 nombres distintos
- `PC.02` → 25 nombres distintos
- `PC.03` → 4 nombres distintos
- `PC.04` → 8 nombres distintos
- `PC.05` → 31 nombres distintos
- `PC.06` → 35 nombres distintos
- `PC.07` → 6 nombres distintos
- `PC.08` → 31 nombres distintos
- `PNC.01` → 12 nombres distintos
- `PNC.02` → 2 nombres distintos
- `PNC.04` → 3 nombres distintos
- `PNC.05` → 11 nombres distintos

### Nombres sospechosos

- `Banco Bci $ Egresos DSI` → caracteres_extraños
- `Banco Santander $` → caracteres_extraños
- `Impuesto de 2° Categoría por Pagar` → caracteres_extraños
- `BANCO DE CHILE N°` → caracteres_extraños
- `BCI N°` → caracteres_extraños
- `Crédito BCI N° 902445` → caracteres_extraños
- `Proveedores Extranjeros US$` → caracteres_extraños
- `I+D` → caracteres_extraños
- `> < valor de inversiones` → caracteres_extraños
- `ctas por cobrar leasing 3° LP` → caracteres_extraños
- `credito impto 2° categoria` → caracteres_extraños
- `crédito impuesto 2° categoría` → caracteres_extraños

### Posibles duplicados (normalización)

- Normalizado: `CLIENTES VENTAS A CREDITO` → ['Clientes Ventas a Credito', 'Clientes Ventas a Crédito']
- Normalizado: `IMPORTACIONES EN TRANSITO` → ['Importaciones en Tránsito', 'importaciones en transito']
- Normalizado: `REVALORIZACION CAPITAL PROPIO` → ['REVALORIZACION CAPITAL PROPIO', 'Revalorización Capital Propio']
- Normalizado: `DEPRECIACION ACTIVOS EN LEASING` → ['Depreciación Activos en Leasing', 'DEPRECIACÍON ACTIVOS EN LEASING']
- Normalizado: `LINEA DE CREDITO BANCO INTERNACIONAL` → ['Línea de Crédito Banco Internacional', 'LINEA DE CRÉDITO BANCO INTERNACIONAL']
- Normalizado: `PROVISION DOCUMENTOS POR RECIBIR` → ['Provisión Documentos por Recibir', 'PROVISION DOCUMENTOS POR RECIBIR']
- Normalizado: `CORRECCION MONETARIA` → ['Corrección Monetaria', 'Correccion monetaria']
- Normalizado: `DEPRECIACION ACUMULADA` → ['DEPRECIACION ACUMULADA', 'DEPRECIACIÓN ACUMULADA']
- Normalizado: `ACTIVOS BIOLOGICOS CORRIENTES` → ['activos biologicos corrientes', 'Activos biológicos corrientes']
- Normalizado: `ASIGNACION FAMILIAR` → ['asignacion familiar', 'asignación familiar']
- Normalizado: `CARTAS DE CREDITO IMPORTACION` → ['cartas de credito importacion', 'cartas de crédito importación']
- Normalizado: `LETRAS EN GARANTIA` → ['letras en garantia', 'letras en garantía']
- Normalizado: `MAYOR VALOR POR RETASACION` → ['mayor valor por retasacion', 'mayor valor por retasación']
- Normalizado: `PARTICIPACION DEVENGADA` → ['participacion devengada', 'participación devengada']
- Normalizado: `CREDITOS A IMPORTACION` → ['creditos a importacion', 'créditos a importación']
- Normalizado: `INSTITUCIONES DE PREVISION` → ['instituciones de prevision', 'instituciones de previsión']
- Normalizado: `PROVISION GASTOS` → ['provision gastos', 'provisión gastos']
- Normalizado: `INDEMNIZACION ANOS DE SERVICIOS` → ['indemnizacion años de servicios', 'indemnización años de servicios']
- Normalizado: `GARANTIAS DE ARRIENDOS RECIBIDAS` → ['garantias de arriendos recibidas', 'garantías de arriendos recibidas']
- Normalizado: `INTERES MINORITARIO` → ['Interes minoritario', 'interés minoritario']
- Normalizado: `RESERVA DE REVALORIZACION` → ['reserva de revalorizacion', 'reserva de revalorización']
- Normalizado: `(-) PERDIDAS ACUMULADAS` → ['(-) perdidas acumuladas', '(-) pérdidas acumuladas']
- Normalizado: `UTILIDADES HISTORICAS` → ['utilidades historicas', 'utilidades históricas']
- Normalizado: `PLUSVALIA` → ['Plusvalía', 'Plusvalia']

## 4. Distribución por Fuente

| Fuente | diccionario.json | actualizado | optimizado | Total |
|--------|-----------------:|------------:|-----------:|------:|
| balances_auditados_ifrs | 76 | 76 | 76 | 228 |
| balances_reales_validado | 436 | 436 | 436 | 1308 |
| balances_reales_validado+conflicto_resuelto | 1 | 1 | 1 | 3 |
| correccion_manual | 7 | 7 | 7 | 21 |
| correccion_v2 | 2 | 2 | 2 | 6 |
| excluido_analista | 3 | 3 | 0 | 6 |
| vaciador_crediticio | 190 | 190 | 190 | 570 |
| validacion_humana | 109 | 66 | 0 | 175 |
| validacion_humana_lote | 2 | 0 | 0 | 2 |

## 5. Inventario de Referencias

| Archivo | Línea | Función | Propósito | Modo | Archivo Dicc |
|---------|-------|---------|-----------|------|-------------|
| `pipeline/homologation_pipeline.py` | 40 | `_load_dictionary (static)` | Lectura del diccionario para clasificación exacta/fuzzy del pipeline principal | lectura | `diccionario_optimizado.json` |
| `pipeline/homologation_pipeline.py` | 74 | `_classify_by_dictionary_exact` | Clasificación exacta: normaliza nombre y busca coincidencia exacta en diccionario | lectura | `diccionario_optimizado.json` |
| `pipeline/homologation_pipeline.py` | 78-99 | `_classify_by_dictionary_fuzzy` | Clasificación fuzzy: usa token_sort_ratio >= 90 contra diccionario | lectura | `diccionario_optimizado.json` |
| `src/db_repository.py` | 70-78 | `_inicializar_json` | Carga JSON como fallback si no hay PostgreSQL | lectura | `diccionario_optimizado.json` |
| `src/db_repository.py` | 90-91 | `diccionario (property)` | Expone el diccionario como lista de dicts | lectura | `diccionario_optimizado.json` |
| `evaluation/homologation_benchmark.py` | 17-20 | `_load_dictionary` | Carga diccionario para benchmark legacy vs pipeline | lectura | `diccionario_optimizado.json` |
| `cargar_datos.py` | 51-53 | `main / upsert_diccionario` | Carga diccionario y hace UPSERT a PostgreSQL | lectura | `diccionario_optimizado.json` |
| `app_validacion.py` | 68-71 | `cargar_diccionario_base` | Carga del diccionario en Streamlit app | lectura | `diccionario.json` |
| `app_validacion.py` | 1111 | `flujo de correcciones (escritura)` | Guarda correcciones de usuario al diccionario.json | escritura | `diccionario.json` |
| `app_validacion.py` | 1267 | `flujo de correcciones lote (escritura)` | Guarda correcciones en lote al diccionario.json | escritura | `diccionario.json` |
| `app_validacion.py` | 1294 | `flujo de correcciones individual (escritura)` | Guarda corrección individual al diccionario.json | escritura | `diccionario.json` |
| `app_validacion.py` | 446 | `interfaz descarga` | Exporta diccionario actual como diccionario_actualizado.json (descargable) | lectura (exportación) | `diccionario.json (sesión)` |
| `diccionario_actualizado.json` | N/A (archivo estático) | `N/A` | Snapshot descargable del diccionario — no referenciado por ningún .py | N/A | `diccionario_actualizado.json` |

## 6. Recomendaciones

### 6.1 Diccionario canónico

- **diccionario_optimizado.json** pierde 45 entradas que existen en diccionario.json (fuente `validacion_humana`/`validacion_humana_lote`). Esto reduce la cobertura del pipeline.
- **diccionario.json** es el archivo canónico: es el que los revisores humanos actualizan mediante la app Streamlit. Tiene 826 entradas, la máxima cobertura de los 3.
- **diccionario_optimizado.json** es el que realmente usa el pipeline de homologación. Está desactualizado: faltan 114 entradas vs. diccionario.json, lo que reduce la cobertura de clasificación.

### 6.2 Módulos a modificar

Para unificar a diccionario.json como fuente única, habría que cambiar la ruta en:
- `pipeline/homologation_pipeline.py:40` — cambiar a `diccionario.json`
- `src/db_repository.py:70` — cambiar a `diccionario.json`
- `evaluation/homologation_benchmark.py:17,91` — cambiar default a `diccionario.json`
- `cargar_datos.py:51` — cambiar a `diccionario.json`
- `app_validacion.py:70` — ya usa `diccionario.json` (no requiere cambio)

### 6.3 Riesgos de la migración

1. **Inconsistencias transitorias:** Si se cambia diccionario_optimizado.json a diccionario.json, el pipeline empezará a clasificar 45 cuentas adicionales, lo cual es positivo pero cambia resultados históricos.
2. **Regresión si se invierte:** Si algún flujo espera menos entradas, pasar de 712 a 826 entradas puede cambiar benchmarks.
3. **Código `__EXCLUIR__`**: Solo presente en 3 archivos con `validacion_humana` en diccionario.json, eliminado en optimizado. Al unificar, reaparecerían 6 entradas con código `__EXCLUIR__` que el pipeline podría intentar clasificar.

### 6.4 Estimación de impacto en cobertura

De las 45 entradas exclusivas de diccionario.json, 43 provienen de `validacion_humana` y 2 de `validacion_humana_lote`. Estas 45 cuentas adicionales aumentarían la cobertura del pipeline en aproximadamente 45/712 = 6.3% sobre la base actual de optimizado. Adicionalmente, al unificar las 781 entradas de actualizado (que incluye 66 `validacion_humana` adicionales removidas en la optimización), la ganancia sería de 69/712 = 9.7%.
Impacto estimado: +6.3% a +9.7% de cobertura de clasificación por diccionario.

