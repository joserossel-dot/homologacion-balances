# Estado actual del proyecto de homologación de balances

## Identificación del documento

| Campo | Valor verificado |
|---|---|
| Fecha del levantamiento | 28 de agosto de 2026 |
| Repositorio | `homologacion-balances` |
| Rama candidata documentada | `codex/mejoras-pendientes-20260826` |
| Commit base del trabajo local | `bcfc4af6294e43e57779714da2fb225fb50567ff` |
| Rama configurada en Render | `codex/release-operativa-neon` |
| Base de la rama candidata | `origin/codex/release-operativa-neon` |
| Diferencia respecto de la base | 10 commits por delante, 0 por detrás |
| Persistencia operativa | PostgreSQL en Neon, con fallback local controlado |
| Interfaz operativa | Streamlit en `app_validacion.py` |

Este documento describe el estado verificable del código candidato. El `README.md` existente conserva información histórica y no debe usarse como inventario funcional actual. Por ejemplo, todavía menciona 52 categorías, 710 cuentas y componentes de persistencia que ya no representan la implementación operativa.

## 1. Resumen ejecutivo

El proyecto recibe balances chilenos en PDF o Excel, extrae cuentas y montos, certifica la consistencia del documento, clasifica las cuentas contra un catálogo homologado, solicita revisión humana cuando existe ambigüedad y genera un balance normalizado con controles de cuadratura y un archivo Excel para integración.

La rama candidata no está limitada a balances auditados. Conserva el flujo general para balances tributarios de ocho columnas, balances clasificados, documentos comparativos de dos períodos, PDF con texto, PDF procesados por OCR y planillas Excel. Las mejoras recientes para balances auditados amplían la selección de páginas, la detección de períodos, la separación entre notas y montos, la continuidad de secciones entre páginas y la extracción de estados financieros clasificados.

El núcleo operativo actual es:

1. `app_validacion.py` como interfaz y coordinador de la sesión.
2. `parser_universal.py` para PDF, OCR y Excel.
3. `pipeline/homologation_pipeline.py` para clasificación.
4. `persistence/neon_store.py` para catálogo, diccionario y aprendizaje.
5. `account_qualification.py` para separar cuentas, controles, totales y texto no contable.
6. `report_presentation.py` y `reporting_integrity.py` para presentación y validación del entregable.

Existen módulos avanzados de inteligencia documental, decisión, cobertura, estructura y Self-QA. No todos coordinan el flujo principal. Structure, Coverage y Self-QA se consumen como controles auxiliares posteriores. Otros componentes permanecen detrás de banderas o como arquitectura paralela y no deben presentarse como capacidades productivas plenamente integradas.

## 2. Objetivo funcional

El resultado esperado es transformar un documento contable heterogéneo en una salida rígida, trazable y utilizable por una empresa financiera:

- identificar empresa, período, moneda y alcance documental;
- extraer cada cuenta y sus importes sin confundir notas, encabezados, subtotales o firmas;
- conservar el origen contable de cada monto;
- clasificar cada cuenta en el catálogo estándar;
- mostrar al analista las dudas, causas y alternativas compatibles;
- aprender únicamente de decisiones humanas explícitas;
- validar activo contra pasivo más patrimonio;
- validar la utilidad del ejercicio contra el estado de resultados;
- emitir un Excel auditable, incluyendo el detalle completo de cuentas desde la fila 26 de la hoja `Resumen`.

## 3. Alcance documental implementado

### 3.1 Entradas

- PDF con capa de texto.
- PDF escaneado que requiere OCR.
- Excel en formatos `.xlsx` y `.xls` admitidos por la interfaz.
- Uno o varios archivos en una misma sesión.
- Documento completo o páginas seleccionadas por el analista.
- Balances de un período y documentos comparativos de hasta dos períodos.
- Valores en pesos, miles, millones, USD u otra unidad informada por el analista.

### 3.2 Familias de documentos cubiertas

- balance tributario de ocho columnas;
- balance tributario con variaciones de encabezados y geometría;
- balance clasificado con secciones de activo, pasivo, patrimonio y resultados;
- estados financieros auditados con notas y dos años comparativos;
- tablas paralelas o dispuestas lado a lado;
- estructuras verticales IFRS;
- Excel con encabezados y columnas variables.

### 3.3 Límites actuales

- La selección de páginas sigue dependiendo de una decisión humana en documentos extensos.
- La detección de estados y años utiliza heurísticas, no una comprensión documental garantizada para cualquier formato futuro.
- El OCR se ejecuta de forma síncrona y puede ser lento en documentos grandes o de mala calidad.
- Los documentos reales privados sólo se prueban si se configura `BALANCE_REAL_TEST_DIR`.
- El repositorio no contiene todavía una matriz pública suficientemente amplia de informes auditados completos.

## 4. Flujo operativo de la aplicación

```mermaid
flowchart TD
    A[Carga de PDF o Excel] --> B[Vista previa del documento]
    B --> C[Selección de todas las páginas o páginas específicas]
    C --> D[Confirmación de empresa, moneda y período]
    D --> E[Extracción PDF, OCR o Excel]
    E --> F{Extracción certificable}
    F -- No --> G[Diagnóstico y corrección con documento visible]
    G --> E
    F -- Sí --> H[Pipeline operativo de clasificación]
    H --> I[Cola de revisión humana]
    I --> J[Balance normalizado]
    J --> K[Cuadratura y validación de utilidad]
    K --> L[Structure, Coverage y Self-QA]
    L --> M[Excel de auditoría o definitivo]
    I --> N[Aprendizaje confirmado en Neon]
```

### 4.1 Vista y alcance antes del análisis

La aplicación muestra el documento antes de extraer y permite:

- recorrer todas sus páginas;
- aplicar zoom y rotación;
- analizar el documento completo;
- seleccionar páginas concretas;
- cambiar posteriormente el alcance seleccionado.

Esta selección es crítica en informes auditados que contienen notas, anexos y más de una presentación de los mismos estados. Procesar indiscriminadamente todo el archivo puede duplicar cuentas o mezclar estados y notas.

### 4.2 Confirmación de datos de la empresa

La etapa de confirmación solicita o permite corregir:

- RUT;
- razón social;
- giro;
- moneda o unidad, con opciones `$`, `M`, `MM`, `USD` y otra editable;
- mes de cierre;
- año;
- número de meses del período, de 1 a 12;
- período comparativo cuando el documento contiene dos años.

El documento original permanece disponible en esta etapa.

### 4.3 Certificación de la extracción

Antes de clasificar, el sistema distingue:

- cuentas de detalle;
- subtotales y totales usados como controles;
- utilidad o pérdida impresa;
- pies de página, firmas y texto legal;
- filas inconsistentes;
- cuentas posiblemente omitidas;
- diferencias entre la suma de cuentas y los controles impresos.

Los subtotales y totales reconocidos no se suman como cuentas. Se conservan como controles de contraste. El analista no debería excluir manualmente un control que el sistema ya reconoció.

Cuando la extracción no puede certificarse, se muestra una tabla editable con:

- separadores de miles para facilitar la lectura;
- causa concreta de la inconsistencia;
- valor leído y corrección contablemente posible;
- opción de excluir texto no contable;
- opción de ingresar manualmente una cuenta omitida;
- documento original en la mitad inferior de la página.

## 5. Parser universal

`parser_universal.py` concentra la extracción operativa.

### 5.1 Capacidades verificadas en código

- detección de años y monedas mediante `detectar_años_y_monedas`;
- separación de columna de nota y columnas monetarias comparativas;
- agrupación geométrica de palabras con tolerancia vertical de 2,5 píxeles;
- división de tablas lado a lado;
- asociación vertical entre glosas e importes;
- continuidad de secciones entre páginas seleccionadas;
- detección de activo, pasivo, patrimonio y estado de resultados;
- lectura de ocho columnas y variantes comparativas;
- números negativos representados con paréntesis contables;
- guiones o rayas usados como cero;
- limpieza de signos y separadores de miles;
- recuperación de filas fragmentadas por OCR;
- filtrado de número de nota para que no sea tratado como monto;
- conservación del período actual y anterior;
- generación de advertencias y nivel de confianza.

### 5.2 OCR

El contenedor instala Poppler y Tesseract en español. La configuración actual usa:

- render base de 200 DPI;
- límite aproximado de 3,5 millones de píxeles por imagen;
- reintento reducido cuando la primera lectura falla;
- timeout principal de 120 segundos por página;
- timeout de reintento de 90 segundos;
- rotación y recuperación por página;
- omisión controlada de una página cuando Tesseract excede el tiempo, con advertencia al analista.

El timeout evita que la aplicación termine con una excepción no controlada, pero el proceso sigue siendo síncrono. El siguiente salto de rendimiento requiere mover OCR a trabajos en segundo plano, guardar resultados por página y reutilizar páginas ya procesadas.

## 6. Calificación de filas y controles impresos

`account_qualification.py` evita que el pipeline trate como cuentas:

- sumas y sumas iguales;
- totales y totales generales;
- subtotales reconocidos;
- utilidad o pérdida de cierre cuando actúa como control;
- encabezados repetidos;
- firmas y bloques legales;
- filas sin valor contable;
- cuentas con monto cero que no requieren revisión.

Esta capa es determinística. Su finalidad es impedir doble conteo y reducir trabajo manual, no clasificar semánticamente una cuenta real.

## 7. Pipeline operativo de clasificación

La clasificación se ejecuta en `pipeline/homologation_pipeline.py`. El orden general es:

1. coincidencia por código original confiable;
2. coincidencia exacta en el diccionario;
3. coincidencia aproximada con el diccionario;
4. reglas regex auditadas;
5. reglas contextuales;
6. fallback por origen contable;
7. revisión humana cuando la evidencia es insuficiente o contradictoria.

El pipeline puede cargar catálogo y diccionario desde Neon. Si Neon no está disponible, utiliza los JSON versionados como respaldo. En el commit candidato, el catálogo local contiene 65 códigos y el diccionario local 916 entradas. La instancia observada en ejecución reportó 67 códigos y 1.122 cuentas en Neon, por lo que la base remota contiene conocimiento adicional.

### 7.1 Origen y naturaleza efectiva

Cada cuenta conserva:

- columna de origen extraída;
- monto con signo;
- naturaleza efectiva;
- código sugerido;
- método de clasificación;
- confianza;
- estado de revisión.

Un monto negativo se interpreta como contra-cuenta. La naturaleza efectiva puede ser distinta de la columna física del documento. Las clasificaciones incompatibles se ocultan por defecto, pero existen excepciones contables explícitas.

### 7.2 Reglas contables especiales

- Depreciación acumulada: código definitivo `ANC.01.01`. Puede originarse como activo negativo o pasivo positivo y debe restar al activo fijo.
- Pérdidas acumuladas: permanecen en patrimonio aunque aparezcan en la columna activo o con signo contrario.
- Ganancias acumuladas negativas: se ofrecen categorías patrimoniales, no categorías de activo corriente.
- Resultados acumulados: `PAT.03` es el único código seleccionable para utilidades retenidas, utilidades acumuladas, pérdidas acumuladas y resultados de ejercicios anteriores. `PAT.09` queda como alias histórico y se normaliza a `PAT.03` al leer o guardar decisiones.
- Reservas: se consideran patrimoniales con signo positivo o negativo.
- Cuentas corrientes de socios en activo: requieren consulta humana o tratamiento patrimonial contrario según el caso.
- Pasivo físico: puede ofrecer pasivo corriente, pasivo no corriente y patrimonio cuando el contexto lo justifica.
- Cuentas de valor cero: no deben alimentar la cola de revisión.

## 8. Cola de revisión humana

La cola muestra por cuenta:

- origen extraído y naturaleza efectiva;
- monto del período elegido;
- monto del período anterior, si existe;
- decisión actual y método;
- hasta tres alternativas compatibles;
- confianza de cada alternativa;
- razón de la coincidencia;
- cuentas semejantes confirmadas en Neon;
- advertencia cuando los mejores candidatos son contradictorios;
- búsqueda ampliada de clasificaciones;
- edición de nombre o cuenta;
- aplicación individual o por lote;
- alcance sólo para el caso o aprendizaje futuro;
- recuperación de una cuenta excluida;
- modificación de una decisión previamente confirmada sin recargar el documento.

Las validaciones individual y por lote aplican las mismas reglas de compatibilidad. Una clasificación que contradice la naturaleza efectiva sólo puede admitirse cuando existe una excepción contable documentada.

## 9. Períodos comparativos

Los balances clasificados y auditados pueden contener dos columnas temporales. La implementación actual:

- detecta hasta dos años en las páginas seleccionadas;
- presenta al analista cuál es el período actual y cuál el anterior;
- permite homologar ambos períodos;
- conserva importes separados por período;
- excluye la columna de notas de auditoría;
- exporta columnas rígidas para ambos períodos.

Si los encabezados de años no se detectan con confianza, la interfaz debe exigir confirmación humana. El sistema no debe asignar silenciosamente un número de nota como importe ni omitir la identidad temporal del monto.

## 10. Persistencia y aprendizaje en Neon

La migración versionada `migrations/001_neon_knowledge.sql` crea:

- `catalogo_maestro`;
- `diccionario_homologacion`;
- `log_validaciones`;
- `historial_diccionario`.

El aprendizaje ocurre cuando el analista confirma explícitamente una decisión con alcance futuro. Se registra:

- cuenta original y normalizada;
- código sugerido y código validado;
- método y confianza de la sugerencia;
- si fue una corrección;
- archivo de origen;
- validador y fecha;
- historial de cambios;
- frecuencia de uso.

La interfaz no escribe directamente los JSON de conocimiento. Los JSON quedan como semilla y fallback versionado.

### 10.1 Lo que Neon todavía no resuelve

No existe una migración operativa para persistir de forma completa:

- documentos cargados;
- ejecuciones de extracción;
- alcance de páginas por documento;
- resultados intermedios;
- correcciones de importes;
- reportes emitidos;
- organizaciones o tenants;
- usuarios, roles o sesiones de analista.

El nombre del analista permanece vacío o usa un valor genérico hasta implementar credenciales.

## 11. Balance normalizado y controles posteriores

La vista de balance normalizado presenta:

- todas las categorías del catálogo, incluso las que quedan en cero;
- activo corriente y no corriente;
- pasivo corriente y no corriente;
- patrimonio;
- estado de resultados ordenado;
- total de activos;
- total de pasivos;
- total de patrimonio;
- pasivo más patrimonio;
- diferencia de cuadratura;
- cobertura monetaria y de cuentas;
- utilidad o pérdida del período;
- comparación entre utilidad contable y resultado homologado;
- causas probables del descuadre;
- acceso para volver a la clasificación humana.

La cuadratura aritmética no demuestra que las clasificaciones sean correctas. `reporting_integrity.py` agrega controles independientes para impedir que una clasificación errónea produzca un entregable aparentemente válido sólo porque activo y pasivo más patrimonio coinciden.

## 12. Structure, Coverage y Self-QA

`pipeline/operational_quality.py` consume una copia del resultado ya clasificado.

- Structure identifica formato de códigos, disposición de columnas y secciones.
- Coverage mide cobertura monetaria, estructural, semántica y documental.
- Self-QA recomienda aprobación o revisión según los hallazgos.

Estos motores no reciben permiso para modificar cuentas o importes. Actualmente funcionan en `shadow mode` salvo que se active explícitamente el control de exportación. La variable `QUALITY_CONTROL_ENFORCE_EXPORT` está configurada en `false` en `render.yaml`.

Cuando se active enforcement, estos controles podrán bloquear la exportación o pedir revisión, pero no reclasificar automáticamente.

## 13. Informe Excel

El exportador genera, según el flujo, las hojas:

- `Resumen`;
- `Estado de Resultados`;
- `Balance Normalizado`;
- `Control de emisión`;
- `Cuentas a corregir`;
- `Decisiones de esta sesión`.

### 13.1 Contrato rígido de integración

La hoja `Resumen` reserva la fila 26 para el encabezado del detalle completo. Desde esa fila se entrega una tabla llamada `CuentasClasificadas` con:

- código homologado;
- nombre homologado;
- código original;
- nombre original;
- valor extraído;
- valor homologado;
- columnas separadas por período cuando existen dos años.

La tabla no contiene celdas combinadas ni subtotales intercalados. Está diseñada para ser consumida por sistemas de empresas financieras.

El informe también registra:

- empresa y RUT;
- período;
- moneda o unidad;
- fecha de proceso;
- documento fuente;
- páginas analizadas;
- estado definitivo o borrador;
- motivos de revisión;
- nombre del analista en blanco hasta definir autenticación.

## 14. Arquitectura por estado de integración

### 14.1 Operativo y conectado al flujo principal

| Componente | Responsabilidad |
|---|---|
| `app_validacion.py` | Interfaz, estado de sesión y flujo principal |
| `parser_universal.py` | Extracción PDF, OCR y Excel |
| `document_scope.py` | Selección y render de páginas |
| `extractor_metadata.py` | Metadatos de empresa y período |
| `account_qualification.py` | Cuentas versus controles y ruido |
| `pipeline/homologation_pipeline.py` | Clasificación operativa |
| `persistence/neon_store.py` | Catálogo, diccionario, historial y validaciones |
| `reporting_integrity.py` | Coherencia del entregable |
| `report_presentation.py` | Presentación y contrato Excel |
| `validation/` | Reglas de validación de sesión y resultado |

### 14.2 Auxiliar o en shadow mode

| Componente | Estado |
|---|---|
| `structure_engine/` | Observa estructura, no modifica el resultado |
| `coverage_engine/` | Calcula cobertura posterior |
| `self_qa_engine/` | Recomienda revisión o aprobación |
| `document_context/` | Contexto para motores auxiliares |
| `shadow/` | Comparaciones sin impacto productivo |

### 14.3 Parcial, experimental o detrás de banderas

| Componente | Observación |
|---|---|
| `decision_engine/` | Motor elaborado disponible, desactivado por defecto |
| `semantic/` | Matcher semántico desactivado por defecto |
| `orchestrator/pipeline_v2.py` | No es el coordinador operativo |
| `document_intelligence/` | Capacidades parciales, no equivalen al flujo principal completo |
| `adapters/` | Adaptadores de la arquitectura paralela |
| `src/api/` | API no utilizada por la aplicación Streamlit desplegada |
| CMCC | Disponible con banderas, producción desactivada |

No se recomienda sustituir el pipeline operativo por `HomologationPipelineV2`. Las capacidades útiles deben integrarse una por una, con pruebas y primero en shadow mode.

## 15. Banderas relevantes

Valores predeterminados observados en `pipeline/features.py`:

| Bandera | Predeterminado |
|---|---:|
| CMCC principal | desactivado |
| CMCC shadow | activado, condicionado al interruptor principal |
| CMCC producción | desactivado |
| filtro de tipo CMCC | desactivado |
| regex fallback | activado |
| matcher semántico | desactivado |
| decision engine | desactivado |

La aplicación implementa además validaciones propias de origen, naturaleza efectiva y compatibilidad. Por ello, una bandera CMCC desactivada no significa que la UI carezca de filtros contables.

## 16. Despliegue

Render construye un contenedor Python 3.12 con:

- Poetry;
- Poppler;
- Tesseract y el idioma español;
- Streamlit en el puerto asignado por Render;
- health check `/_stcore/health`;
- `DATABASE_URL` como secreto;
- contexto de build sin `.env`, historial Git, pruebas, reportes ni documentos contables locales;
- despliegue automático desactivado.

`render.yaml`, `APP_RELEASE_BRANCH` y el workflow de certificación apuntan a `codex/mejoras-pendientes-20260826`. El despliegue automático de Render permanece desactivado. Después de aprobar pruebas y el preflight de Neon, el workflow verifica que el hash certificado siga siendo la punta de la rama y solicita a Render ese commit exacto. La ejecución espera el estado `live` y falla si Render informa otro hash o un estado de error.

El repositorio no contiene credenciales. GitHub Actions requiere estos secretos:

- `NEON_DATABASE_URL`;
- `RENDER_API_KEY`;
- `RENDER_SERVICE_ID`.

`RENDER_GIT_COMMIT`, mostrado por la interfaz, sigue siendo la evidencia de la versión activa. `APP_RELEASE_BRANCH` identifica la línea de release configurada.

## 17. Pruebas y evidencia del corte

### 17.1 Suite mantenida

La suite ubicada en `tests/` contiene pruebas de:

- revisión manual individual y por lote;
- contra-cuentas y naturaleza efectiva;
- parser universal y resiliencia OCR;
- selección documental;
- balances comparativos y monedas;
- matrices documentales sintéticas;
- controles de extracción;
- clasificación y aprendizaje;
- Neon y preflight;
- Structure, Coverage y Self-QA;
- informes y cuadratura;
- regresiones de documentos reportados.

En la verificación más reciente, `pytest tests -q` completó 956 pruebas aprobadas, 17 omitidas y 3 advertencias. La prueba privada adicional se omite cuando no está definido `BALANCE_REAL_TEST_DIR`.

### 17.2 Saneamiento del simulador histórico

El archivo raíz `test_orquestador.py` no contenía pruebas ni aserciones: era un simulador manual que importaba `db_repository` y `src.core.orquestador`, componentes que ya no coordinan la aplicación operativa. Su nombre provocaba que pytest lo recogiera y fallara durante la colección.

El simulador fue retirado explícitamente y reemplazado por `scripts/smoke_pipeline.py`, conectado a `pipeline.homologation_pipeline.HomologationPipeline`. No se modificó la configuración de descubrimiento de pytest para ocultar el problema. El nuevo script acepta la ruta de un PDF o Excel y muestra un resumen del procesamiento sin incluir el detalle completo de cuentas.

### 17.3 Fixtures reales versionados

El repositorio incluye cinco fixtures reales o representativos en `tests/fixtures/balances_reales/`:

- Balance General Agrícola 2013;
- Balance 2017 Mar Vivo;
- Balance 2017 Naviera Orca;
- EEFF 2017 Los Maitenes;
- Pre-Balance Inagal 2020.

La matriz privada añade Parque Cultural, London38, Afuminsal y Fundación Arte y Solidaridad. `tests/fixtures/private_release_matrix.json` declara el archivo, las páginas que forman el estado contable y los resultados esperados sin incorporar los PDF privados a Git. `scripts/certify_local_corpus.py --manifest` aplica ese alcance, registra cada comprobación en JSON y devuelve error si un caso obligatorio no satisface sus expectativas.

La ejecución verificada sobre el corpus privado obtuvo:

- Parque Cultural: cumple;
- London38, limitado a la página contable declarada: cumple;
- Afuminsal: cumple la cuadratura final, el resultado esperado y la extracción de capital social;
- Fundación Arte y Solidaridad: recupera los controles finales y aísla una única fila ambigua, `IMPTOS. POR PAGAR`, para revisión humana. La matriz comprueba expresamente que no aparezcan otras filas inconsistentes.

Una regresión privada adicional modifica únicamente el crédito ambiguo sobre las cuentas ya extraídas y verifica que la recertificación queda sin filas inconsistentes, con controles finales válidos y sin volver a ejecutar el parser.

Las pruebas privadas de pytest siguen requiriendo `BALANCE_REAL_TEST_DIR`. Sin esa variable se omiten; el manifiesto puede ejecutarse explícitamente con:

```bash
python3 scripts/certify_local_corpus.py "$BALANCE_REAL_TEST_DIR" \
  --manifest tests/fixtures/private_release_matrix.json \
  --output /tmp/homologacion-release-matrix.json
```

### 17.4 Gold por cuenta y candidatos auditados

La comprobación agregada anterior no basta para acreditar completitud. El
certificador conserva ahora la huella SHA-256 del documento, los períodos y
monedas detectados y una instantánea de todas las filas, incluidos controles,
montos por período, montos por columna, origen y código homologado.

La opción `--write-gold-candidates` genera un libro por documento con las hojas
`Resumen`, `Cuentas`, `Controles` y `Advertencias`. Cada fila comienza con
`Estado_revision=PENDIENTE`. El libro no puede usarse como Gold mientras exista
una sola fila que no esté marcada `APROBADO` o `EXCLUIR`. `APROBADO` significa
que la fila debe existir exactamente. `EXCLUIR` identifica ruido que el parser
debe dejar de emitir; si la salida todavía contiene esa fila, la recertificación
la detecta como adicional y falla. `PENDIENTE` y `CORREGIR` mantienen bloqueado
el Gold. Después de la revisión humana, el manifiesto puede declarar
`gold_file`; una fila faltante, adicional o distinta hace fallar la
recertificación.

```bash
python3 scripts/certify_local_corpus.py "$BALANCE_REAL_TEST_DIR" \
  --manifest tests/fixtures/private_gold_candidate_matrix.json \
  --output /tmp/homologacion-gold-candidates.json \
  --write-gold-candidates "$BALANCE_GOLD_DIR"

python3 scripts/certify_local_corpus.py "$BALANCE_REAL_TEST_DIR" \
  --manifest tests/fixtures/private_gold_candidate_matrix.json \
  --gold-root "$BALANCE_GOLD_DIR" \
  --output /tmp/homologacion-gold-recertification.json
```

Una búsqueda local deduplicada por contenido encontró 528 documentos únicos en
las carpetas primarias examinadas: 449 PDF, 78 XLSX y 1 XLS. De ellos, 115 tienen
señales nominales de estados auditados o IFRS. Se revisaron visualmente, fila por
fila, tres disposiciones comparativas no cubiertas por la matriz privada
anterior:

- ABS 2022-2021: estados auditados en páginas separadas y tabla de contenidos;
- Cosemar 2016-2015: Activo, Pasivo y Resultado en páginas distintas, expresado
  en miles de pesos;
- Purefruit 2018-2017: estado combinado en una página, USD y negativos entre
  paréntesis.

Los libros Gold aprobados se mantienen fuera del repositorio y el manifiesto
sólo conserva nombre, selección de páginas, huella SHA-256 y nombre del Gold.
Los tres casos detectan ambos períodos y la moneda esperada. La recertificación
exacta del 28 de agosto de 2026 pasa en los tres, sin filas faltantes,
adicionales ni distintas respecto de los Gold aprobados. Desde esa revisión son
casos obligatorios del release gate.

Correcciones acreditadas por los Gold:

- ABS: recupera 37 cuentas, incluidas las filas del estado de resultados de la
  página 10, sin convertir encabezados o texto truncado en cuentas;
- Cosemar: recupera 42 cuentas y clasifica automáticamente 32, sin encabezados
  o bandas adicionales;
- Purefruit: recupera 41 cuentas y clasifica automáticamente 28, sin
  encabezados o bandas adicionales.

El directorio privado usado en esta estación es
`Downloads/homologacion-balances/recertificacion_gold_20260827/`. Debe
configurarse mediante `BALANCE_REAL_TEST_DIR` y `BALANCE_GOLD_DIR` en cada
entorno que ejecute la recertificación. No debe versionarse el contenido de los
balances ni de los libros Gold.

## 18. Riesgos pendientes antes de producción

### Prioridad crítica

1. Verificar en la interfaz que la corrección humana de `IMPTOS. POR PAGAR` recertifique Fundación Arte y Solidaridad sin volver a procesar el documento.
2. Mantener ABS, Cosemar y Purefruit en el release gate exacto y ampliar la
   matriz sin relajar sus comparaciones por cuenta, monto y período.
3. Configurar `RENDER_API_KEY` y `RENDER_SERVICE_ID` en GitHub y validar una ejecución real del release gate hasta estado `live` con el mismo hash certificado.
4. Definir autenticación, analista responsable y segregación de acceso antes de manejar información contable sensible de terceros.

### Prioridad alta

1. Persistir documentos, ejecuciones, correcciones y reportes en Neon o almacenamiento durable.
2. Ejecutar OCR en segundo plano con progreso, caché por página y reintentos recuperables.
3. Ampliar el Gold con Excel, OCR y estados auditados de dos períodos después de
   aplicar el mismo control de huella y aprobación completa.
4. Medir precisión por cuenta, cobertura monetaria, falsos positivos y tiempo de intervención humana.
5. Activar gradualmente Coverage y Self-QA como gate de exportación cuando exista evidencia suficiente.
6. Separar o retirar la arquitectura paralela que no tiene consumidor operativo.

### Prioridad media

1. Actualizar `README.md` y metadatos de Poetry.
2. Eliminar los respaldos que escriben JSON y SQLite dentro del código desplegado, o moverlos a almacenamiento durable, antes de ejecutar el contenedor con un usuario no root.
3. Ejecutar el contenedor con un usuario no root una vez resueltas esas escrituras.
4. Añadir observabilidad de tiempos por página, OCR, clasificación y descarga.

## 19. Criterio propuesto para lanzamiento

La aplicación puede considerarse candidata a un piloto controlado cuando se cumpla todo lo siguiente:

- suite completa, incluida la raíz, sin errores de colección;
- matriz de documentos estándar, ocho columnas, clasificados, OCR, rotados, comparativos y auditados aprobada;
- exactitud de cuentas y montos revisada contra resultados esperados;
- cuadratura e integridad del estado de resultados aprobadas;
- aprendizaje Neon verificado sin duplicados ni contaminación del catálogo;
- exportación bloqueada ante hallazgos críticos;
- commit desplegado igual al commit certificado;
- respaldo y recuperación de Neon probados;
- autenticación y trazabilidad de analista definidas;
- procedimiento de rollback documentado y ensayado.

Con la evidencia actual, la rama candidata es apta para pruebas funcionales intensivas y un piloto con supervisión. No existe evidencia suficiente para afirmar que procesa correctamente cualquier documento ni para autorizar una producción desatendida.

## 20. Operación local

Requisitos:

- Python 3.12;
- Poetry;
- Poppler;
- Tesseract con idioma español;
- `DATABASE_URL` para Neon, si se desea persistencia remota.

Comandos principales:

```bash
poetry install
poetry run streamlit run app_validacion.py
poetry run pytest tests -q
poetry run python scripts/neon_preflight.py
```

La URL y las credenciales de Neon no deben versionarse. Deben configurarse como variables de entorno locales o secretos de Render y GitHub.

## 21. Fuente de verdad del corte

Para evaluar el estado actual se deben consultar, en este orden:

1. commit desplegado mostrado por la interfaz;
2. rama y commit candidatos indicados al inicio de este documento;
3. pruebas ejecutadas sobre ese commit;
4. `render.yaml` y el release gate;
5. migraciones versionadas de Neon;
6. código del pipeline operativo;
7. documentación histórica sólo como contexto.

Una etiqueta de rama, un HTTP 200 o una cuadratura aritmética aislada no certifican por sí solos la calidad contable del resultado.
