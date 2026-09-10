# INFORME DE BENCHMARK Y REVISIÓN: CLASIFICACIÓN Y EXCEPCIONES VERIFICADAS (B2)

> **NOTA DE ESTADO (HISTÓRICO / COMPLEMENTARIO):**
> Este informe documenta los resultados experimentales del benchmark de clasificación B2 (22 casos). El documento canónico consolidado para revisión y preparación de selección es `reports/pilot_coverage/FORMATOS_VERIFICADOS.md`.

**Fecha:** 2026-09-10
**Rama:** `codex/mejoras-pendientes-20260826`
**HEAD:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536`
**Repositorio:** `.` (Proyecto Operativo)
**Entorno de Ejecución:** macOS / Python 3.14.5 / pytest 9.1.1
**Aislamiento Real:** Verificado (Sockets de red bloqueados, Neon fail-closed, SQLite temporal en `/tmp`)

---

## 1. Verificación Inicial de Entorno y Git

Se verificó el estado del repositorio de forma estricta:
- **Ruta Operativa:** `.` (directorio de trabajo raíz)
- **Rama Operativa:** `codex/mejoras-pendientes-20260826`
- **HEAD de Referencia:** `9bc7892ada367defbebbc3ea34a7aefacf8bf536` (verificado coincidente).
- **Remoto:** `origin https://github.com/joserossel-dot/homologacion-balances.git`
- **Estado de Trabajo:** Se mantuvieron intactos los archivos productivos, diccionarios oficiales (`diccionario.json`, `catalogo_maestro.json`), base de datos Gold y cambios preexistentes en `docs/ROADMAP_PRODUCCION_ONPREMISE.md`.

---

## 2. Aislamiento Real Comprobado

Para garantizar un benchmark 100% determinista y seguro:
1. **Bloqueo Preventivo de Red:** Se interceptó `socket.socket.connect` a nivel de proceso en `benchmark_runner.py` con una rutina *fail-closed* que levanta `RuntimeError` ante cualquier intento de conexión TCP/UDP externa.
2. **Inhabilitación de Neon:** Se purgó `DATABASE_URL` del entorno, se forzó `AUTH_ENFORCEMENT = "staging"` y se sobreescribió `NeonKnowledgeStore._connect` para impedir cualquier acceso transaccional a la base de datos remota.
3. **Almacenamiento SQLite Temporal:** El motor `LearningEngine` y el constructor Gold se instancian exclusivamente en un directorio efímero (`tempfile.TemporaryDirectory()`), asegurando que no se lean ni muten estados históricos aprendidos por usuarios.
4. **Estado de Sesión Aislado:** Se limpia `st.session_state` al inicio de cada ejecución de prueba para evitar contaminación de estado entre pruebas.

---

## 3. Correcciones Metodológicas (B2)

### 3.1 Medición Única y Unificada (Test y Runner Sincronizados)
- Se eliminó la divergencia donde el test llamaba a `_alternativas_revision` con sugerencia vacía y confianza cero mientras el runner pasaba datos del pipeline.
- Se definió `run_benchmark()` en `experiments/pilot_coverage/classification/benchmark_runner.py` como la **única fuente de verdad** del experimento, y los tests en `test_confidence_benchmark.py` verifican directamente sus resultados.

### 3.2 Corrección del Contrato de Motor en Sugerencias UI
- **Hallazgo Crítico:** En el experimento anterior, se pasaba `HomologationPipeline` como `motor` a `_alternativas_revision`. Dado que `HomologationPipeline` no posee los atributos `dic_lista` ni `dic_exacto` (propios de `MotorHibridoLocal`), la búsqueda en el diccionario quedaba completamente omitida, atribuyéndose falsamente las ausencias de Top-3 a limitaciones del algoritmo difuso.
- **Corrección:** Se configuró `MotorHibridoLocal(diccionario)` como el motor de sugerencias en estricta conformidad con el contrato de `_tab_revision` en `app_validacion.py`.
- **Efecto Medido:** La tasa Top-3 subió de **64.3%** a **78.6% (11/14)**, logrando recuperar correctamente cuentas como `SYN01` (*"Caja Chica..."* $\rightarrow$ `AC.01`) y `PAT01` (*"Pérdidas Acumuladas..."* $\rightarrow$ `PAT.03`) directamente en Top-1.

### 3.3 Tratamiento de Cuentas Ambiguas, Desconocidas y Controles
Se establecieron distinciones explícitas para evitar que cualquier cuenta sin etiqueta se catalogue genéricamente como revisión justificada:
- **Automatizaciones Indebidas ($0$):** Casos sin código estándar o que exigían abstención donde el clasificador hubiese confirmado erróneamente de forma automática.
- **Revisiones Justificadas ($13$):** Cuentas con sinónimos complejos, contra-activos, patrimonio negativo, ambiguas, desconocidas o con conflicto de columna que efectivamente exigieron revisión humana.
- **Controles Aritméticos Correctamente Separados ($2$):** Líneas de totales (`TOT01`, `TOT02`) identificadas como control y excluidas de las cuentas de detalle.
- **Controles Tratados como Cuenta ($0$):** Cero líneas de control fueron clasificadas como partidas contables de detalle.

### 3.4 Pruebas de Revisión Real y Control de Emisión
En `test_review_exceptions.py`:
- **Corrección de Extracción:** Se probó que al editar el nombre, columna y monto mediante las funciones auxiliares (`_aplicar_edicion_monto_periodos`, `_origen_efectivo`, `_etiqueta_origen`), se invalida el binding de certificación documental (`df.attrs.pop("certification_binding")`), se conserva `requiere_revision = True` (sin confirmar indebidamente la categoría) y se preservan las demás filas intactas.
- **Confirmación de Categoría:** Se verificó la validación contable (`_codigo_compatible_con_origen`), el registro de auditoría (`_registrar_decision`), la asignación de `metodo = 'validacion_humana'` con `requiere_revision = False`, y el aislamiento de filas.
- **Bloqueos de Emisión Aislados:** Se evaluaron por separado e independientemente:
  1. Bloqueo por certificación documental inválida.
  2. Bloqueo por cuenta pendiente de revisión.
  3. Bloqueo por descuadratura contable ($Activo \neq Pasivo + Patrimonio$).
- **Desbloqueo Explícito:** Se probó la autorización definitiva (`emision["definitivo"] is True`, 0 motivos de bloqueo) sobre un balance sintético cuadrado ($Activo = 1.000.000$; $Pasivo + Patrimonio = 1.000.000$) y debidamente certificado.
- **Alcance Declarado:** Se declara expresamente que estas pruebas ejercitan las funciones de servicio y contratos de validación de la aplicación. La interfaz interactiva gráfica completa de Streamlit permanece declarada como cobertura de servicio/unidad.

---

## 4. Resultados Detallados por Caso (22 Casos Evaluados)

| ID | Nombre de Cuenta | Categoría | Columna | Monto | Código Esperado | Código Obtenido | Método Pipeline | Conf. Clasif. | Conf. Extr. | Auto? | Rev? | Decisión Evaluada | Sugerencias Top-3 (Motor UI) | Origen Documental |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **EX01** | Caja | Exacta | ACTIVO | 100.000 | `AC.01` | `AC.01` | `dictionary_exact` | 0.98 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['AC.01']` | Catálogo Maestro AC.01 (Caja y Bancos) |
| **EX02** | Banco de Chile | Exacta | ACTIVO | 5.000.000 | `AC.01` | `AC.01` | `dictionary_exact` | 0.98 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['AC.01']` | Catálogo Maestro AC.01 (Caja y Bancos) |
| **EX03** | Clientes | Exacta | ACTIVO | 2.500.000 | `AC.03` | `AC.03` | `dictionary_exact` | 0.98 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['AC.03']` | Catálogo Maestro AC.03 (Clientes) |
| **EX04** | Proveedores Nacionales | Exacta | PASIVO | 1.200.000 | `PC.01` | `PC.01` | `dictionary_exact` | 0.98 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['PC.01', 'PNC.05', 'PC.09']` | Catálogo Maestro PC.01 (Proveedores) |
| **EX05** | Capital Pagado | Exacta | PATRIMONIO | 10.000.000 | `PAT.01` | `PAT.01` | `dictionary_exact` | 0.98 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['PAT.01', 'PAT.02', 'PAT.06']` | Catálogo Maestro PAT.01 (Capital Pagado) |
| **SYN01** | Caja Chica Sucursal Centro | Sinónimo | ACTIVO | 50.000 | `AC.01` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.01']` | Subcuenta de efectivo -> AC.01 |
| **SYN02** | Deudores por Ventas Comerciales | Sinónimo | ACTIVO | 800.000 | `AC.03` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.07', 'ANC.05', 'AC.10']` | Variante comercial -> AC.03 |
| **SYN03** | Acreedores Comerciales Varios | Sinónimo | PASIVO | 450.000 | `PC.01` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['PC.08', 'PNC.05', 'PC.03']` | Pasivo con proveedores -> PC.01 |
| **AMB01** | Otras Cuentas | Ambiguo | DESCONOCIDO | 10.000 | `null` | `None` | `unclassified` | 0.00 | 0.80 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.07', 'PC.08', 'ANC.06']` | Genérico sin desglose -> Revisión |
| **AMB02** | Varios y Ajustes | Ambiguo | DESCONOCIDO | 25.000 | `null` | `None` | `unclassified` | 0.00 | 0.80 | No | Sí | **REVISION_JUSTIFICADA** | `['PAT.02', 'ER.04', 'AC.07']` | Genérico ambiguo -> Revisión |
| **AMB03** | Provisión General | Ambiguo | PASIVO | 300.000 | `null` | `None` | `unclassified` | 0.00 | 0.90 | No | Sí | **REVISION_JUSTIFICADA** | `['PC.08', 'PC.06', 'PC.09']` | Provisión no especificada -> Revisión |
| **CA01** | Depreciación Acumulada Maquinarias | Contra-cuenta | PASIVO | -500.000 | `ANC.01.01` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['ANC.01', 'ANC.01.01']` | Contra-activo Activo Fijo (ANC.01.01) |
| **CA02** | Amortización Acumulada Intangibles | Contra-cuenta | PASIVO | -200.000 | `ANC.03` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['ANC.03', 'ANC.01', 'ANC.01.01']` | Contra-activo Intangibles (ANC.03) |
| **TAX01** | Activos por impuestos diferidos | Imp. Diferidos | ACTIVO | 150.000 | `ANC.09` | `ANC.09` | `audited_statement_label` | 0.96 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['ANC.06', 'ANC.09', 'AC.08']` | Catálogo ANC.09 (Audited label) |
| **TAX02** | Pasivos por impuestos diferidos | Imp. Diferidos | PASIVO | 180.000 | `PNC.06` | `PNC.06` | `audited_statement_label` | 0.96 | 1.00 | Sí | No | **AUTOMATICA_CORRECTA** | `['PNC.06', 'PNC.05', 'PC.05']` | Catálogo PNC.06 (Audited label) |
| **PAT01** | Pérdidas Acumuladas Años Anteriores | Patr. Negativo | ACTIVO | -1.200.000 | `PAT.03` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['PAT.03']` | Resultados acumulados deudores -> PAT.03 |
| **TOT01** | Total Activo Circulante | Total | ACTIVO | 15.000.000 | `null` | `AC.08` | `origin_fallback` | 0.55 | 1.00 | No | Sí | **CONTROL_ARITMETICO_SEPARADO** | `['AC.08', 'ANC.01', 'ANC.06']` | Control de agregación (Excluido) |
| **TOT02** | Total Pasivo y Patrimonio | Total | PASIVO | 15.000.000 | `null` | `PC.08` | `origin_fallback` | 0.55 | 1.00 | No | Sí | **CONTROL_ARITMETICO_SEPARADO** | `['PAT.05', 'PNC.03', 'PC.08']` | Control de balance (Excluido) |
| **UNK01** | Fondo Extraordinario Proyecto Alfa | Desconocido | DESCONOCIDO | 750.000 | `null` | `None` | `unclassified` | 0.00 | 0.90 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.07', 'AC.01']` | Cuenta fuera de catálogo -> Revisión |
| **UNK02** | Depósito Transitorio Sin Aplicar | Desconocido | DESCONOCIDO | 120.000 | `null` | `None` | `unclassified` | 0.00 | 0.90 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.03']` | Transitoria no homologable -> Revisión |
| **CONF01** | Ingresos por Ventas de Servicios | Conflicto | PASIVO | 500.000 | `null` | `None` | `unclassified` | 0.00 | 0.70 | No | Sí | **REVISION_JUSTIFICADA** | `[]` | Conflicto nombre (ER.01) vs col. Pasivo |
| **UNC01** | Cuenta Corriente Mercantil Histórica | Saldo Cero | ACTIVO | 0 | `AC.08` | `None` | `unclassified` | 0.00 | 0.95 | No | Sí | **REVISION_JUSTIFICADA** | `['AC.06S', 'AC.07', 'AC.03']` | Saldo cero (excluido de cola de revisión) |

---

## 5. Métricas Consolidadas con Denominadores Explícitos

### 5.1 Desglose Poblacional
- **Total Casos en Benchmark ($N$):** 22
- **Cuentas de Detalle con Código Verificable ($N_{\text{clasificables}}$):** 14
- **Cuentas Ambiguas, Desconocidas o con Conflicto ($N_{\text{ambiguas}}$):** 6
- **Líneas de Control / Totales ($N_{\text{controles}}$):** 2

### 5.2 Métricas de Automatización y Clasificación

$$\text{Exactitud de Código} = \frac{\text{Auto Correctas}}{\text{Auto Correctas} + \text{Auto Incorrectas}} = \frac{7}{7 + 0} = \mathbf{100.0\%}$$

$$\text{Cobertura Automática} = \frac{\text{Auto Correctas}}{N_{\text{clasificables}}} = \frac{7}{14} = \mathbf{50.0\%}$$

$$\text{Tasa de Automatización Indebida} = \frac{\text{Automatizaciones Indebidas}}{N_{\text{ambiguas}}} = \frac{0}{6} = \mathbf{0.0\%}$$

- **Clasificaciones Automáticas Correctas:** **7 / 14 (50.0%)** (5 cuentas exactas + 2 etiquetas auditadas).
- **Clasificaciones Automáticas Incorrectas (Falsos Positivos de Código):** **0 / 14 (0.0%)**.
- **Automatizaciones Indebidas (en casos que exigían abstención):** **0 / 6 (0.0%)**.
- **Revisiones Justificadas:** **13 / 13 (100.0%)**.
- **Revisiones Evitables:** **0 / 14 (0.0%)**.
- **Controles Aritméticos Correctamente Separados:** **2 / 2 (100.0%)**.

### 5.3 Métricas de Sugerencias Asistidas en UI (`_alternativas_revision`)

Para las 14 cuentas evaluables con código estándar ($N_{\text{clasificables}} = 14$):

$$\text{Tasa Top-1} = \frac{9}{14} = \mathbf{64.3\%} \qquad \text{Tasa Top-3} = \frac{11}{14} = \mathbf{78.6\%}$$

- **Aciertos Top-1 (9 cuentas):** `EX01` (AC.01), `EX02` (AC.01), `EX03` (AC.03), `EX04` (PC.01), `EX05` (PAT.01), `SYN01` (AC.01), `CA02` (ANC.03), `TAX02` (PNC.06), `PAT01` (PAT.03).
- **Aciertos Top-3 (11 cuentas):** Las 9 anteriores más `CA01` (ANC.01.01 en posición 2) y `TAX01` (ANC.09 en posición 2).
- **Cuentas fuera de Top-3 (3 cuentas):**
  1. `SYN02` (*"Deudores por Ventas Comerciales"*): Las palabras adicionales desplazan la similitud hacia `AC.07` y `AC.10`.
  2. `SYN03` (*"Acreedores Comerciales Varios"*): No alcanza el umbral mínimo frente a *"Proveedores"*.
  3. `UNC01` (*"Cuenta Corriente Mercantil Histórica"*): Saldo cero; no rankea `AC.08`.

---

## 6. Conclusiones del Informe Anterior que se Retiran o Corrigen

1. **Retiro de la Hipótesis de Falla del Fuzzy en `SYN01` y `PAT01`:** En el informe previo se afirmó que `SYN01` (*"Caja Chica..."*) y `PAT01` (*"Pérdidas Acumuladas..."*) quedaban fuera de Top-3 por limitaciones del token ratio. Se comprobó que dicha exclusión era un defecto del test (al pasar `HomologationPipeline` sin diccionario en lugar de `MotorHibridoLocal`). Con el contrato de UI correcto, ambas cuentas aciertan en **Top-1**.
2. **Corrección de la Tasa Top-3:** La tasa real medida en UI sube de **64.3%** a **78.6%**.
3. **Formalización de Fórmulas y Denominadores:** Se eliminaron las condiciones ad-hoc `conf >= 0.85` en el test, sustituyéndolas por la ejecución unificada y trazable de `benchmark_runner.py`.

---

## 7. Tres Recomendaciones Basadas en Evidencia

1. **Incorporación de Sinónimos de Pasivos Comerciales en Diccionario Local:**
   - *Evidencia:* `SYN03` (*"Acreedores Comerciales Varios"*) no alcanza similitud con *"Proveedores"*.
   - *Acción:* Agregar la entrada canónica *"Acreedores Comerciales"* asociada a `PC.01`.
2. **Token Matcher Parcial para Variantes de Cuentas por Cobrar:**
   - *Evidencia:* `SYN02` (*"Deudores por Ventas Comerciales"*) dispersa la puntuación por contener 4 tokens.
   - *Acción:* Permitir coincidencia ponderada si contiene la raíz *"Deudores por Ventas"* vinculada a `AC.03`.
3. **Explicabilidad en Tooltips para Contra-Activos:**
   - *Evidencia:* `CA01` y `CA02` provienen de columna Pasivo pero rankean en `ANC`.
   - *Acción:* Mostrar en la sugerencia: *"Contra-activo con saldo acreedor compatible con Activo No Corriente"*.

---

## 8. Lista Exacta de Archivos Intervenidos

### Modificados (Propiedad Exclusiva)
1. `tests/experiments/pilot_coverage/test_confidence_benchmark.py`
2. `tests/experiments/pilot_coverage/test_review_exceptions.py`

### Creados en Rutas Autorizadas
1. `tests/experiments/pilot_coverage/fixtures/classification/benchmark_cases.json`
2. `experiments/pilot_coverage/classification/benchmark_runner.py`
3. `reports/pilot_coverage/CLASIFICACION_VERIFICADA.md`
