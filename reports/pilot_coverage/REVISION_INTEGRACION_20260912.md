# Revisión de integración del 12 de septiembre de 2026

## Base y publicación

Rama: `codex/mejoras-pendientes-20260826`.
Base inicial auditada: `bea81e42ebe2015236f042589195b662c8e7ad44`.
Último commit local y remoto verificado: `5fa64af00b5bcd92e05e2f82f0e87b81800c8e2e`.

Durante la integración, una operación concurrente publicó `5fa64af` con
`app_validacion.py` y `parser_universal.py`, incluyendo correcciones que este
equipo todavía verificaba. Codex no ejecutó ese commit ni push. Los demás
ajustes y sus pruebas permanecieron locales. La primera regresión fue detenida;
su resultado parcial no se usa como certificación.

CI del commit publicado: ejecución `34699468429`, 4 fallidas, 1716 aprobadas,
26 omitidas. Fallan inventario arquitectónico, dos expectativas del benchmark
y contrato del visor. Seguridad y smoke on-premise aprobaron. El despliegue
certificado quedó bloqueado. Fuente:
https://github.com/joserossel-dot/homologacion-balances/actions/runs/34699468429

## Correcciones integradas

- Compatibilidad: activo no permite patrimonio por origen solamente; conserva
  las excepciones patrimoniales y de socios específicas ya comprobadas.
- Revisión compacta: restablece controles y formulario de nueva categoría.
  El guardado fallido no confirma ni incorpora al catálogo la categoría nueva.
- Normalizador experimental: elimina clave duplicada y evita contaminación de
  configuración entre instancias. Las dos entradas duplicadas de `impuestos`
  tenían el mismo valor; no se comprobó un cambio de clasificación por esa clave.
- Reglas especiales nuevas: permanecen experimentales y desconectadas. Sus
  patrones amplios de socios, relacionadas, patentes e impuestos diferidos
  requieren validación antes de una integración productiva.
- Benchmark: verifica el décimo acierto, SYN02 a AC.03, mediante catálogo y
  evidencia por caso. No cambia el umbral operativo ni convierte esa sugerencia
  en confirmación automática. B2: Top-1 10/14, Top-3 12/14, automática 7/14.
- Higiene: respaldo local de diccionario ignorado, revisión estática y espacios
  corregidos en el alcance auditado, informe exploratorio rotulado histórico.

## Hallazgo adicional del último commit

La expresión nueva de controles incluía nombres como `Utilidades o pérdidas
acumuladas` y `Utilidad/Pérdida acumulada`. Su reconocimiento como total podía
sacar cuentas patrimoniales del detalle. El ajuste local conserva el control
de cierre `Utilidad/Pérdida` y sus variantes de ejercicio/año, pero excluye de
esa regla los saldos acumulados. También retira la excepción de identidad
monetaria basada en coincidencias parciales del nombre.

Nueve casos sintéticos verifican controles de cierre, conservación de cuentas
y rechazo de identidades monetarias incorrectas. Con la suite de certificación
de extracción: 167 pruebas aprobadas.

## Verificación final

Entorno local Python 3.12. Variables de conexión de producción vacías durante
las pruebas. Recolección comprobada: 1761 pruebas.

- Carpeta original: 1744 aprobadas, 11 omitidas y 6 fallidas en 222,09 s.
  Cinco fallos dependen de entradas esperadas en `gold_standard.db`; el sexto
  exige que no exista `gold_standard_runtime.db`. Ambos archivos ya existían
  desde el 11 de septiembre. Se conservaron intactos. Estas pruebas con la
  base local no quedan aprobadas ni se usan como evidencia Gold vigente.
- Copia temporal del HEAD más todos los cambios y pruebas locales, sin bases
  ni configuración privada: 1735 aprobadas, 25 omitidas y 1 fallida en 222,78 s.
  El único fallo fue `test_gitignore_reglas_especificas_y_rechazo_generales`:
  la copia por archivo Git no contenía `.git` (salida 128). Se inicializó Git
  únicamente en esa copia temporal y se repitió la prueba: 1 aprobada en 0,98 s.
  No se cambió código para corregir ese fallo de preparación del entorno.
- No se presenta lo anterior como una única ejecución integral con cero fallos.
  Los cuatro fallos de CI del commit publicado no se reprodujeron con los
  ajustes locales. La ejecución completa en GitHub del siguiente commit sigue
  pendiente, al igual que la recertificación privada.
- Ruff del alcance funcional modificado y `git diff --check`: aprobados.
- HEAD y huella del diff rastreado permanecieron estables durante la prueba
  aislada: `213399ba800219f15857657b7c503fa13868e64458bf83563a79fb27fb8c4171`.

No se ejecutaron migraciones, cambios en Neon ni despliegues desde esta revisión.
La recertificación documental privada y CI sobre el futuro commit consolidado
son comprobaciones posteriores, no sustituidas por esta revisión local.

## Consolidación y certificación completa posterior

Se repitió la suite íntegra en la copia aislada con Git ya inicializado:
**1736 aprobadas, 25 omitidas, 0 fallidas, 3 advertencias, 221,24 segundos**.
La copia contiene el HEAD publicado más los cambios locales y las pruebas
nuevas. No incorpora las bases Gold/runtime del escritorio ni credenciales.

La matriz documental obligatoria aprobó **2/3**. El tercer caso conserva
una diferencia de **11.420.298** en Débitos y en Créditos frente al subtotal
impreso; saldos, columnas finales y resultado coinciden, pero eso no sustituye
la validación de movimientos. El caso opcional quedó parcial y no coincide
con su expectativa histórica de una cuenta inconsistente específica.

Los libros de la antigua carpeta `gold` tienen schema 1. Se localizaron los
libros finales aprobados de septiembre, se verificó schema 2 y se usaron copias
temporales con los nombres requeridos por el manifiesto, sin editar originales
ni cambiar resultados esperados. La recertificación Gold final aprobó **0/3**:

| Caso, orden del manifiesto | Filas reales / esperadas | Estado | Sin clasificar |
| --- | --- | --- | --- |
| Gold 1 | 36 / 37 | parcial | 6 |
| Gold 2 | 41 / 42 | parcial | 4 |
| Gold 3 | 43 / 41 | no evaluable | 5 |

Hay filas fusionadas con encabezados, filas faltantes/adicionales y códigos
distintos al Gold, entre ellos impuestos diferidos, patrimonio y partidas no
corrientes. No se atribuye el conjunto de estas diferencias al último commit
sin una comparación documental con la base anterior. Tampoco se rebajan las
expectativas para obtener una aprobación.

**Conclusión de esa ejecución inicial: consolidación técnica comprobada;
certificación de liberación bloqueada por documentos reales.** Corregir extracción y clasificación sobre
estos casos antes de emitir una atestación o desplegar el candidato.

## Selección propuesta para conservar las correcciones

### Diagnóstico documental posterior

El caso obligatorio con diferencia simétrica en Debe/Haber fue contrastado
visualmente con su PDF. Los movimientos de las filas visibles coinciden con
la extracción, pero su suma no reproduce el total de movimientos impreso.
La coincidencia de los saldos no autoriza a modificar los movimientos ni a
certificar el documento como íntegramente consistente. Se requiere aclaración
del documento fuente para certificar sus movimientos. También se identificó
una fusión independiente entre el resultado de cierre y el total final que
requiere corrección del parser.

En los casos Gold se verificó que algunos encabezados de sección quedan
fusionados con subtotales: las filas posteriores heredan una sección corriente
incorrecta. La reparación debe preservar los controles aritméticos y recuperar
el contexto, sin rebajar las restricciones de compatibilidad contable.

### Recertificación tras reparación de secciones

La nueva ejecución con los mismos libros Gold aprobados y sin modificar sus
expectativas aprobó **3/3** casos. Filas: **37, 42 y 41**. Los tres estados son
`certificada` y todos sus controles `expectation_checks` aprobaron, incluida
la comparación exacta de filas y metadatos. Esto reemplaza el resultado Gold
0/3 de la ejecución inicial documentada arriba.

Se corrigió también la interpretación de glifos horizontales marcados como
no verticales por el PDF, que impedía aprovechar su geometría. La inferencia
patrimonial desde una columna física PASIVO requiere sección PAT explícita.
La regresión integral posterior a estas reparaciones aprobó **1763 pruebas**,
con **25 omitidas**, **0 fallidas** y **3 advertencias** en 223 segundos.
El gate de recolección verificó **1788 pruebas**. Se ejecutó en copia aislada,
sin bases runtime locales ni conexión Neon. Las advertencias corresponden a
una deprecación de pandas, no a errores de las pruebas. Después se retiró una
variable sin uso de un test, sin cambiar su comportamiento.

Al separar el resultado de cierre del total final, el caso con diferencia de
movimientos conserva 31 filas y activa una política preexistente:
`movimientos_no_exhaustivos` permite certificar las columnas finales cuando
sus controles independientes concuerdan. No se modificó esa política. Por
tanto, su estado `certificada` no acredita la integridad de Debe/Haber. Se
corrigió el aviso para declarar esa limitación sin inventar una causa para
la diferencia. La certificación de movimientos sigue sin resolverse.

Validación estática on-premise: 50 pruebas aprobadas. La prueba real de
contenedores se ejecutó posteriormente con Docker 29.5.3. El smoke oficial
aprobó sus 8 etapas: contrato Compose, construcción e inicio aislados, salud
HTTPS con CA local explícita, persistencia consumida por la aplicación,
durabilidad tras reinicio, respaldo cifrado de `app_runtime`, restauración y
recuperación de salud. Resultado: `SMOKE ON-PREMISE (evaluation): APROBADO`.
La aceptación de identidad corporativa sigue siendo un control separado.

La matriz documental obligatoria también aprueba **3/3**, bajo esa política
de certificación de columnas finales. El caso opcional permanece `parcial`
y no cumple su expectativa de cuenta inconsistente: la lista real está
vacía. No se modificó el manifiesto para ocultar esta diferencia. Este caso
requiere revisión separada antes de ampliar el alcance documental declarado.

Todos los archivos siguientes corresponden a cambios de esta revisión. No
se realizó staging, commit ni push. La selección no equivale a aprobación de
liberación:

```text
.gitignore
account_name_normalizer.py
docs/architecture/module_pruning_plan.md
experiments/pilot_coverage/classification/benchmark_classifier_isolated.py
parser_universal.py
parsers/account_type_resolver.py
pipeline/homologation_pipeline.py
reports/pilot_coverage/INFORME_EXPERIMENTOS_PILOTO_20260910.md
reports/pilot_coverage/BENCHMARK_REVALIDACION_20260912.md
reports/pilot_coverage/REVISION_INTEGRACION_20260912.md
special_account_rules.py
tests/experiments/pilot_coverage/test_benchmark_isolated.py
tests/experiments/pilot_coverage/test_confidence_benchmark.py
tests/test_audit_findings_h1_h2.py
tests/test_audit_findings_h3.py
tests/test_audit_plan_p0_p1_p2.py
tests/test_audited_section_classification.py
tests/test_closing_result_labels.py
tests/test_comparative_extraction_boundaries.py
tests/test_experimental_account_knowledge.py
tests/test_extraction_certification.py
tests/test_extraction_controls.py
tests/test_extraction_ui_improvements.py
tests/test_manual_revision.py
tests/test_report_integrity.py
```

Incluye correcciones funcionales, pruebas de regresión, higiene estática,
aislamiento del respaldo local y evidencia documental sin filas privadas.
Excluye PDFs, libros Gold, bases de datos, respaldo de diccionario, credenciales
y resultados JSON privados. La interfaz ya forma parte de `5fa64af` y no tiene
cambios adicionales locales en esta selección.
