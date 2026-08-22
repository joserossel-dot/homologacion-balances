# Plan para una extracción y homologación documental universal y segura

## Resumen ejecutivo

El repositorio ya contiene gran parte de los componentes conceptuales necesarios:
Structure Engine, Document Intelligence, extractores especializados, Pipeline V2,
Validation Engine, Coverage Engine, Self-QA, revisión humana, persistencia y
aprendizaje. El problema principal no es la ausencia de ideas, sino su integración.

La aplicación operativa todavía ejecuta el parser universal y el pipeline clásico.
Los motores nuevos se prueban mayormente de forma aislada y no certifican el dato
extraído antes de homologarlo. Además, la selección de extractor especializado se
anota, pero normalmente no modifica la estrategia efectiva de extracción; el layout
dinámico permanece desactivado.

La meta realista no debe formularse como “todo documento siempre se procesa”. Debe
ser: **todo documento se identifica, se intenta extraer por estrategias trazables y
sólo se homologa automáticamente cuando la extracción queda certificada; en caso
contrario se detiene con un diagnóstico accionable y revisión humana**.

## Evidencia revisada

### Inventario documental

El repositorio de trabajo histórico contiene 1.160 archivos PDF/Excel distribuidos
entre ARCHIVE, HOLDOUT, PROCESSING, REJECTED, STRESS, TRAINING,
`balance_structures_lab`, `edge_cases` y `validacion`. Es una base valiosa, pero no
es todavía un benchmark gobernado:

- `HOLDOUT_README.md` declara 20 casos, mientras la carpeta contiene actualmente
  140 PDF.
- Hay duplicados o documentos casi idénticos repartidos entre familias.
- `document_mining.json` declara 725 documentos y 23 familias, pero la familia más
  grande agrupa 279 casos como estructura/tipo/código desconocidos.
- Los diez mayores clusters concentran 94,62 % del corpus, aunque parte de esa
  concentración proviene de fingerprints poco discriminantes.
- Los perfiles de extracción varían desde buena cobertura hasta baja precisión o
  tamaños de muestra insuficientes.

### Matriz exploratoria de documentos reales

La siguiente ejecución es diagnóstica, no una certificación contable. Mide si el
parser devuelve filas y cómo asigna sus columnas; todavía faltan totales Gold por
documento para determinar fidelidad completa.

| Caso | Tipo observable | Páginas | Texto nativo | Cuentas | No cero | Señal relevante |
|---|---|---:|---:|---:|---:|---|
| Balance 2017 - Don Hugo S.A. | Balance tributario nativo de 10 columnas | 2 | 17.103 caracteres | 253 | 165 | Extrae muchas filas, pero fragmenta montos y confunde columnas; el resultado conocido no cuadra. |
| Balance Com Jeremias Diciembre 2018 | Balance comercial sin códigos estables | 3 | 7.939 | 103 | 102 | La extracción es abundante, pero requiere Gold para acreditar completitud y clasificación. |
| BCE TRIBUTARIO 2024 INGEFIRE | Escaneo OCR de 8 columnas | 3 | 0 | 126 | 88 | OCR funciona con confianza reducida; debe certificarse contra totales impresos. |
| BALANCE CLASIFICADO AICSA 2019 | Balance clasificado | 3 | 3.373 | 101 | 23 | 77 filas quedan con origen desconocido; no debe homologarse automáticamente. |
| EEFF Inmob. LA bajo IFRS 2018 | Estados financieros IFRS | 5 | 6.271 | 136 | 77 | 44 filas sin origen y distribución inverosímil; requiere estrategia propia para EEFF. |
| Anexo 1 ACT FIJO MEGAMERCADOS 2019 | Anexo de activo fijo, no balance | 2 | 9.762 | 94 | 92 | El parser lo acepta como balance; falta un gate de tipo documental. |

El caso Don Hugo expone un defecto estructural concreto: el documento contiene
Código + Cuenta + ocho columnas monetarias. El extractor tabular actual espera una
fila de nueve celdas (nombre + ocho montos), mientras `pdfplumber` colapsa las filas
de este PDF Quartz. La extracción de texto plano introduce espacios dentro de los
montos. Las heurísticas posteriores interpretan esos fragmentos como columnas
válidas y entregan una salida plausible pero incorrecta.

## Componentes existentes y decisión de reutilización

| Componente | Estado encontrado | Decisión |
|---|---|---|
| `ParserPDF` | Operativo, con OCR, heurísticas y correcciones recientes | Conservar como una estrategia candidata, no como autoridad única. |
| Document Intelligence / Extractor Factory | Detecta familias y selecciona extractores | Integrar de verdad: la selección debe ejecutar el extractor y registrar su evidencia. |
| Extractores `aicsa`, `gonzagri`, `nogales`, `wilug` | Implementaciones especializadas limitadas | Mantener como plugins; medirlos contra Gold antes de promoverlos. |
| Profile-driven extraction | Genera hints por familia | Activar primero en shadow mode; no promover perfiles con baja evidencia. |
| Pipeline V2 | Orquesta SIE, DIE, parser, KB, decisiones, validación, cobertura y QA | Convertirlo en la única fachada, luego de corregir sus contratos y gates. |
| Validation Engine | Estructura, subtotales y ecuaciones | Reutilizar, pero alimentarlo con totales impresos independientes. |
| Coverage Engine | Cobertura monetaria, estructural, semántica y documental | Corregir circularidad: no inferir total y explicado desde las mismas cuentas. |
| Self-QA | Agrega gates y riesgo | Reutilizar como gate final; hoy no reemplaza una certificación de extracción. |
| Revisión humana | Ya permite correcciones contables y reapertura | Extender a corrección de filas/columnas, no sólo clasificación. |
| Neon / aprendizaje | Persistencia disponible | Aprender sólo de casos certificados y aprobados; versionar evidencia y reversión. |

## Fallas críticas que deben resolverse antes de escalar

1. **No existe un contrato canónico de extracción.** Se reduce cada fila demasiado
   pronto a un nombre, un monto y una naturaleza. Deben preservarse todas las
   celdas, coordenadas, página, estrategia y confianza.
2. **No hay certificación independiente de totales.** El sistema debe detectar y
   comparar Debe, Haber, Saldo Deudor, Saldo Acreedor, Activo, Pasivo/Patrimonio,
   Pérdidas y Ganancias contra los totales impresos.
3. **Algunos gates son circulares.** Si Coverage no recibe totales externos, infiere
   tanto total como explicado desde las mismas cuentas y puede producir 100 %.
4. **La ecuación de resultado es tautológica.** Actualmente calcula ambos lados con
   la misma expresión, por lo que siempre pasa si existen ingresos/costos/gastos.
5. **El tipo documental no bloquea.** Un anexo de activo fijo puede continuar como
   balance y contaminar la homologación o el aprendizaje.
6. **La familia detectada no gobierna realmente la extracción.** La factory anota
   la decisión y el layout dinámico está desactivado por defecto.
7. **La prueba de release es sintética.** Cubre cinco formas simuladas, pero no
   certifica documentos reales, sus filas ni sus totales.
8. **La taxonomía mezcla columna física y naturaleza contable.** “Pasivo” físico
   debe admitir Pasivo y Patrimonio, y excepciones contables controladas como
   contra-activos; la naturaleza efectiva debe quedar explícita y auditable.

## Arquitectura objetivo

### 1. Ingreso y clasificación del documento

- Validar archivo, cifrado, páginas, tamaño, MIME y daños.
- Distinguir balance tributario, balance clasificado, EEFF, auxiliar/anexo y no
  financiero.
- Detectar texto nativo, tabla vectorial, escaneo, rotación, idioma y calidad.
- Rechazar o enrutar anexos antes del parser de balances.

### 2. Concurso de estrategias de extracción

Ejecutar una o más estrategias según el perfil:

- Excel nativo por encabezados y tipos de celda.
- PDF por palabras y coordenadas X/Y.
- PDF por líneas y bordes de tabla.
- Parser de 8 columnas y parser de Código + Cuenta + 8 columnas.
- Extractor especializado de familia.
- OCR por región/columna como fallback, no OCR de página completa por defecto.

Cada candidato entrega el mismo `RawLedgerDocument`, con evidencia y métricas. Un
selector elige al ganador por integridad, no por cantidad de filas.

### 3. Modelo canónico sin pérdida

Por cada fila conservar:

- texto y código originales;
- las ocho columnas monetarias, incluidas las de valor cero;
- página, bounding boxes y encabezados asociados;
- valores normalizados y tokens originales;
- estrategia, familia, versión y confianza;
- banderas de total, subtotal, encabezado, nota o cuenta;
- transformaciones aplicadas y advertencias.

Los ceros se preservan como evidencia en extracción, pero se excluyen de la cola de
clasificación salvo que participen en una inconsistencia o subtotal.

### 4. Certificación de extracción

Antes de clasificar, exigir:

- Debe = Haber dentro de tolerancia;
- Saldo Deudor = Saldo Acreedor;
- Activo + Pérdidas = Pasivo/Patrimonio + Ganancias, según el formato;
- suma de filas compatible con subtotales impresos;
- cobertura de filas y monto sobre denominadores independientes;
- ausencia de montos fragmentados, columnas desplazadas y duplicación de filas;
- correspondencia entre encabezado físico y posición X.

Si no pasa, no se genera un balance homologado definitivo. Se muestra el documento,
la tabla extraída, la diferencia exacta y acciones para corregir columna, valor,
tipo de fila o estrategia.

### 5. Interpretación contable y homologación

- Derivar naturaleza efectiva desde columna, signo y reglas de contra-cuenta.
- Pasivo físico ofrece Pasivo y Patrimonio; permite excepciones justificadas como
  depreciación acumulada contra activo fijo.
- Cuentas corrientes de socios en activo siempre requieren consulta humana o una
  propuesta explícita PAT.10 con signo contrario, nunca aprendizaje silencioso.
- Filtrar clasificaciones incompatibles, pero permitir “buscar más” mediante una
  excepción explicada y registrada.
- Separar confianza de extracción de confianza de clasificación.

### 6. Reconciliación y revisión humana

- Mostrar cuadratura del documento original y del balance homologado por separado.
- Explicar el descuadre por cuenta, columna y efecto monetario.
- Permitir volver a extracción o clasificación sin reprocesar todo el documento.
- Guardar cada corrección como evento versionado y reversible.

### 7. Aprendizaje gobernado

Sólo incorporar al diccionario o a perfiles de documento cuando:

- la extracción fue certificada;
- la homologación cuadró;
- un humano aprobó excepciones;
- no existe conflicto abierto;
- se conserva fuente, versión, usuario y timestamp.

El aprendizaje debe separar: alias de cuenta, regla contable, familia documental y
perfil de extracción. Una corrección de clasificación no debe alterar por sí sola
la geometría de extracción.

## Secuencia recomendada de desarrollo

### P0 - Evitar resultados falsamente válidos

1. Crear `RawLedgerDocument` y preservar todas las columnas/coordenadas.
2. Implementar extractor Código + Cuenta + 8 montos y corregir Don Hugo.
3. Implementar totales impresos y `ExtractionCertification` independiente.
4. Corregir Coverage circular y la ecuación tautológica de resultados.
5. Bloquear anexos/no balances y fallar cerrado cuando no hay certificación.
6. Crear Gold real mínimo con filas y totales para 12 documentos.

### P1 - Integrar lo que ya existe

7. Hacer que Pipeline V2 sea la fachada única detrás de un feature flag.
8. Ejecutar Structure, Document Intelligence, Validation, Coverage y Self-QA en
   shadow mode, comparando su decisión con el flujo operativo.
9. Hacer efectiva la selección de extractor; registrar candidato, ganador y razón.
10. Activar gates sólo cuando la matriz real alcance los umbrales.

### P2 - Ampliar cobertura de formatos

11. Crear extractores por familia para los clusters que cubren 80-90 % del corpus.
12. Separar rutas para tributario, clasificado, IFRS y auxiliares.
13. Implementar OCR segmentado, presupuesto de tiempo por página y degradación
    controlada para evitar timeouts globales.
14. Incorporar Excel como fuente de primera clase y no como conversión visual.
15. Depurar fingerprints, duplicados y perfiles con evidencia insuficiente.

### P3 - Operación y aprendizaje continuo

16. Activar aprendizaje sólo sobre casos certificados y aprobados.
17. Crear tablero de cobertura por familia, extractor y causa de rechazo.
18. Promover nuevas familias mediante shadow -> revisión -> canary -> activo.
19. Establecer rollback de reglas/diccionario y auditoría completa en Neon.
20. Bloquear despliegues si el commit, la matriz Gold o las migraciones no coinciden
    con la versión certificada.

## Matriz Gold inicial propuesta

Cada caso debe tener conteo de cuentas, filas originales, ocho columnas, subtotales,
totales finales, resultado y clasificación esperada cuando corresponda.

1. Don Hugo 2017: PDF nativo Quartz, Código + Cuenta + 8 columnas.
2. Jeremías 2018: balance sin códigos confiables.
3. Ingefire 2021/2024: escaneado OCR de 8 columnas.
4. AICSA 2019: balance clasificado y extractor especializado.
5. EEFF IFRS 2018: estados financieros, no balance tributario clásico.
6. Un balance de doble columna real.
7. Un documento rotado.
8. Un Excel tributario nativo.
9. Un caso con depreciación acumulada en activo negativo.
10. Un caso con depreciación acumulada en pasivo positivo.
11. Un caso con cuenta corriente socios/retiros PAT.10.
12. Un anexo/no balance que obligatoriamente debe rechazarse o enrutar distinto.

HOLDOUT debe quedar congelado, deduplicado y excluido de reglas/aprendizaje. TRAINING
y VALIDATION deben tener manifiestos versionados con hash, familia, permisos y Gold.

## Gates de aceptación

No promover una familia o extractor a producción sin cumplir, sobre casos reales:

- 100 % de documentos identificados como balance/no balance correctamente en Gold.
- 100 % de totales impresos recuperados en balances compatibles.
- 100 % de cuadratura original reproducida dentro de tolerancia.
- al menos 99,5 % de cobertura monetaria de extracción;
- al menos 99 % de precisión de columna ponderada por monto;
- cero homologaciones definitivas cuando falla la certificación;
- cero cuentas de monto cero en la cola humana normal;
- trazabilidad completa desde celda homologada hasta página/coordenada original;
- timeout aislado por página y respuesta parcial diagnóstica, nunca caída completa;
- clasificación medida separadamente de extracción.

## Métricas operativas mínimas

- tasa de documentos certificados automáticamente;
- tasa de rechazo correcto y falso rechazo;
- cobertura monetaria y precisión de columnas por familia;
- tiempo p50/p95 por página y estrategia;
- páginas que requieren OCR y timeouts recuperados;
- cuentas y monto enviados a revisión humana;
- descuadres originales y descuadres introducidos por homologación;
- reglas aprendidas, conflictos, reversión y antigüedad;
- desempeño por commit, versión de extractor y familia documental.

## Próximo incremento ejecutable

El siguiente sprint no debe intentar activar todos los motores. Debe entregar una
cadena vertical certificable para Don Hugo y tres formatos adicionales:

1. modelo canónico sin pérdida;
2. extractor por coordenadas para 10 columnas;
3. lectura independiente de totales;
4. gate de certificación y UI de fallo cerrado;
5. cuatro fixtures reales con Gold y regresión;
6. instrumentación shadow para comparar parser clásico, profile-driven y
   especializado.

Cuando ese incremento reproduzca filas, columnas y totales reales, Pipeline V2
puede empezar a reemplazar gradualmente al flujo clásico. Conectar primero todos los
motores sin corregir el contrato de extracción sólo automatizaría el error actual.

## Avance implementado en el primer incremento P0

- `CuentaRaw` preserva ahora las ocho columnas monetarias cuando están disponibles.
- Existe una estrategia geométrica basada en encabezados y coordenadas, aplicable
  con o sin código, con sinónimos Debe/Haber, Débitos/Créditos y encabezados de una
  o varias líneas.
- El layout detectado se reutiliza en páginas continuadas sin encabezado.
- Las tablas nativas completas tienen prioridad; coordenadas se usa como fallback
  cuando la tabla está colapsada o ausente.
- La certificación compara cada columna contra el subtotal impreso, verifica las
  identidades internas de cada fila y controla la fila TOTALES IGUALES.
- Una certificación fallida detiene la homologación y muestra causas y filas.
- Los formatos todavía no evaluables continúan con una advertencia visible.
- Los anexos u otros documentos identificados sin encabezados de balance se
  detienen antes de homologar.
- La matriz real confirmó que Jeremías conserva su extractor tabular, Ingefire su
  ruta OCR y Don Hugo usa la nueva estrategia geométrica, pero permanece bloqueado
  porque sus filas todavía no reproducen los subtotales impresos.

### Avance del segundo incremento

- Se reconocen SUMAS/SUMAS IGUALES como subtotales y TOTALES/TOTAL GENERAL como
  cierres equivalentes a las variantes ya soportadas.
- El estado `certificada` exige reproducir subtotales, identidades por fila y
  totales finales; Jeremías cumple actualmente estos tres controles.
- El estado `parcial` se usa para balances clasificados/IFRS cuando Total Activos
  coincide con Total Pasivos y Patrimonio, sin afirmar que el detalle esté completo.
- AICSA e IFRS pasan a `parcial` y deben mantener revisión humana de sus cuentas.
- El OCR usa PSM 6 para el detalle y una segunda lectura PSM 4 sólo en la última
  página para intentar recuperar totales tabulares sin duplicar el costo completo.
- Una extracción de ocho columnas sin subtotal pasa a `fallida` si sus filas violan
  identidades internas o contradicen una fila final disponible; Ingefire se bloquea
  por esta razón en vez de continuar con datos dañados.

### Avance del tercer incremento

- La segunda lectura OCR dejó de ejecutarse incondicionalmente en la última página:
  sólo se solicita cuando faltan filas numéricas, estructura de tabla o controles.
- Los candidatos PSM 6 y PSM 4 se comparan con una métrica independiente de empresa
  que considera encabezados, densidad de filas, ocho columnas y totales impresos.
- Si la lectura de tabla es materialmente mejor se selecciona completa; si sólo
  recupera SUMAS/TOTALES, se fusionan esos controles sin perder el detalle principal.
- La estrategia elegida queda registrada como advertencia diagnóstica, de modo que
  precisión y tiempo puedan medirse por documento y página.

### Avance del cuarto incremento

- Los balances clasificados recuperan la naturaleza de sus cuentas desde secciones
  explícitas: activos, pasivos/patrimonio, ingresos y gastos.
- La evidencia de sección corrige la heurística de últimas columnas cuando el PDF
  no conserva una tabla de ocho columnas; una columna realmente observada no se
  sobrescribe.
- Se reconocen variantes corrientes, no corrientes, circulantes, activos fijos,
  otros activos y pasivos a largo plazo.
- La propagación se detiene al cerrar Pasivos y Patrimonio o al comenzar otro estado
  financiero, evitando contaminar flujos de efectivo y cambios patrimoniales.
- La matriz real mejora AICSA e IFRS con orígenes recuperados, pero mantiene estado
  `parcial`: la ecuación final cuadra y el detalle aún requiere controles de sección.

### Avance del quinto incremento

- Los encabezados de sección se enlazan con sus subtotales impresos y se compara el
  detalle no totalizado contenido entre ambos.
- Una ecuación final cuadrada ya no basta para continuar si una sección no reproduce
  su total: el documento pasa a `fallida` y expone la diferencia por sección.
- AICSA e IFRS quedan correctamente bloqueados porque sus extracciones actuales
  cuadran al final, pero no reproducen todo el detalle interno.
- Se descartan metadatos numéricos frecuentes como nivel del informe y período
  "Desde ... a ...", que antes podían ingresar como cuentas.

### Avance del sexto incremento

- Los encabezados `Actual/Anterior` y pares de años activan un modo comparativo
  explícito: el monto principal siempre corresponde al período actual, incluso si
  es cero, y ambos valores quedan preservados en `montos_periodos`.
- Las referencias de notas como `6.1.2` se separan de los importes y ya no se
  interpretan como una tercera columna monetaria.
- La utilidad o pérdida del ejercicio se incluye como componente del patrimonio
  al validar su subtotal, aunque conserve su marca de resultado/total para otros
  flujos.
- AICSA reproduce la ecuación final y seis controles de sección; IFRS reproduce la
  ecuación y el control de activos. Ambos vuelven a `parcial`, ahora con el período
  actual seleccionado y diferencias internas dentro de tolerancia.

### Avance del séptimo incremento

- La UI conserva monto actual y anterior, identifica visualmente que se trabaja con
  el período actual y muestra el comparativo anterior en la cola de revisión.
- Las cuentas cuyo período actual es cero no ingresan a revisión aunque el período
  anterior tenga saldo.
- La matriz integral mantiene Jeremías certificado; AICSA e IFRS parciales con
  controles reproducidos; Don Hugo e Ingefire permanecen bloqueados por fallas de
  extracción reales, sin permitir homologaciones engañosas.

### Avance del octavo incremento

- La geometría separa tokens monetarios de texto antes de asignar columnas, de modo
  que nombres largos pueden invadir visualmente una columna sin absorber su monto.
- Cuando el PDF daña una celda de movimiento, sólo se reconstruye Débito/Crédito si
  saldo unilateral y columna clasificada confirman exactamente la misma cifra.
- Toda cifra reconstruida queda registrada por fila y visible en la revisión humana;
  el documento se clasifica como `parcial`, nunca como extracción certificada.
- Don Hugo reproduce ahora las ocho sumas impresas sin diferencia; una única fila
  tiene Débitos reconstruidos por 4.732.547 y queda obligatoriamente en revisión.

### Avance del noveno incremento

- Tesseract entrega además TSV con palabras y coordenadas; esas posiciones se
  convierten en celdas de ocho columnas antes de interpretar montos.
- El detector tolera signos `$` adheridos y errores OCR recurrentes en encabezados,
  como `Acreeedor` y `Pasiwo`.
- El render OCR sube de 165 a 200 DPI: en Ingefire reduce las filas internamente
  inconsistentes de 48 a 22, sin volver al costo de 250 DPI que causaba timeouts.
- Ingefire permanece correctamente bloqueado: la mejora es material, pero 22 filas
  todavía no cumplen identidades contables y no deben homologarse automáticamente.
