# Prueba de aceptación funcional del 8 de septiembre de 2026

Este documento contiene pruebas por ejecutar. Sus resultados están pendientes.
La aprobación Docker B2 no sustituye la revisión contable descrita aquí.

## Preparación con el encargado de instalación

Solicite al encargado una dirección de acceso al ambiente de pruebas y una
cuenta individual. Pídale que registre la versión exacta y prepare copias
autorizadas de los documentos. No use una instalación productiva para provocar
errores. Las decisiones de prueba deben guardarse sólo para ese caso; si la
pantalla no permite ese alcance, deténgase y registre el impedimento.

Complete los campos en blanco antes de comenzar:

| Dato | Completar |
|---|---|
| Empresa y ambiente de prueba | |
| Versión/commit, informado por el encargado | |
| Fecha y hora de inicio | |
| Analista y cuenta individual utilizada | |
| Segundo revisor contable | |
| Responsable de resolver incidentes | |
| Carpeta privada autorizada para evidencias | |

Prepare al menos tres documentos: balance tributario de ocho columnas, estado
auditado con dos períodos y PDF escaneado. Pueden cubrir varios casos de la
tabla siguiente. Identifique para cada uno las páginas a usar, moneda, escala
(por ejemplo pesos o miles de pesos), períodos y totales impresos. Mantenga
el PDF abierto junto a la aplicación. No suponga que una cifra del documento
está correcta sólo porque el sistema coincide con ella; anote inconsistencias
del propio documento por separado.

## Cómo registrar un resultado

Use `APROBADO`, `RECHAZADO` o `NO EJECUTADO`. Un caso no ejecutado no cuenta
como aprobado. Si el documento no contiene la cuenta necesaria, utilice otro
documento autorizado y anote el cambio. Los nombres de controles pueden variar
según la versión; si no encuentra la acción indicada, registre la pantalla y
el bloqueo, sin intentar compensarlo cambiando un monto correcto.

Para cada caso complete esta ficha y guárdela en la carpeta privada:

| Campo | Completar |
|---|---|
| Identificador del caso | |
| Documento, páginas, moneda/escala y período | |
| Cuenta o fila revisada | |
| Valor impreso y valor mostrado | |
| Clasificación esperada y clasificación mostrada | |
| Acción realizada y resultado observado | |
| Captura antes/después y archivo de reporte, si aplica | |
| Estado, fecha, analista y segundo revisor | |
| Incidente y responsable, cuando corresponda | |

No publique capturas con información contable en un repositorio o canal abierto.

## Casos obligatorios

| Caso | Acciones del analista | Criterio de aceptación |
|---|---|---|
| U01. Ocho columnas | Cargue el balance tributario. Confirme empresa, moneda/escala y período. Compare Debe, Haber, saldos, Activo, Pasivo, Pérdidas y Ganancias en el PDF y la extracción; revise también los totales. | Cada cifra corresponde a su columna; discrepancias identifican la fila y columna afectadas. Un error en Debe/Haber no invita a modificar un Activo correcto. Si la política permite continuar con advertencia, ésta queda visible y trazable. |
| U02. Dos períodos y páginas | En el auditado elija sólo las páginas de balance y resultados. Solicite ambos períodos. Compare una cuenta con nota numérica cercana y otra con importe cero o negativo, en ambos años. | Los años aparecen identificados; las notas no se incorporan al monto. No se mezclan páginas omitidas ni columnas de distintos años. Moneda y escala son consistentes en pantalla y reporte. |
| U03. OCR y corrección | Cargue el escaneado. Compare las cuentas señaladas con el PDF ampliado. Corrija una cifra realmente mal leída, si existe, y verifique nuevamente. | El valor corregido coincide con el documento; queda trazabilidad y se actualiza el diagnóstico. Una lectura ilegible o no resuelta no se presenta como certificación definitiva. Si no existe error, complete el caso con otro escaneado autorizado que sí lo tenga. |
| U04. Subtotales | Localice un grupo, por ejemplo Bancos, y sus cuentas hijas. Revise la clasificación del grupo y de las subcuentas y avance hasta el reporte. | El subtotal se conserva como control y no se suma de nuevo al detalle. Si se hereda clasificación, las subcuentas continúan identificables con sus montos. No se requiere clasificar el subtotal como si fuera otra cuenta sumable. |
| U05. Contra-cuentas | Use un documento con depreciación acumulada en Pasivo o en Activo negativo. Revise además pérdidas acumuladas o reservas negativas cuando existan; use otro documento si es necesario. | Depreciación acumulada admite `ANC.01.01` y resta del activo sin duplicarse. Se distingue de depreciación del ejercicio. Pérdidas acumuladas y reservas conservan su naturaleza patrimonial y el signo correspondiente, con origen extraído visible. |
| U06. Decisión manual editable | Clasifique una cuenta sólo para el caso. Avance y vuelva a revisión. Cambie la decisión, confirme y vuelva al reporte. | Puede modificar una decisión previa. La cuenta conserva trazabilidad y el reporte usa la nueva decisión. La certificación anterior se invalida y requiere nueva validación. La prueba no modifica el diccionario global. |
| U07. Cuenta omitida | Identifique una cuenta presente en PDF y ausente de extracción; solicite al encargado un caso de prueba adecuado si no la encuentra. Ingrésela manualmente con su monto, período y origen verificables. | La cuenta se incorpora una sola vez y conserva su procedencia manual. Los controles se recalculan. No se certifica una cuenta sin evidencia suficiente del documento. |
| U08. Resultado y atribución | Revise ingresos, costos, gastos, resultado antes de impuestos, impuestos y resultado final. Si el auditado tiene controladora/no controladores, compare también su distribución por año. | Los subtotales no se suman como gastos/ingresos adicionales. Los signos y el resultado coinciden con el documento; las participaciones no se contabilizan dos veces. Si falta depreciación separada, el desglose ingresado desde notas reduce los costos/gastos de origen y mantiene el resultado total. |
| U09. Reporte e integración | Genere el reporte después de resolver controles. Abra el Excel. Compare totales y una muestra de detalle contra el PDF, y revise las clasificaciones completas, orden, período, moneda, fecha y analista. | Activo coincide con Pasivo más Patrimonio y el estado de resultados se concilia. El detalle conserva código, nombre y valor extraído de cada cuenta. El formato acordado de la hoja Resumen, incluido el bloque de detalle desde la fila acordada, coincide con el contrato aprobado. Si ese contrato no está firmado, registre pendiente. |
| U10. Bloqueo del entregable | En una copia de prueba, después de validar, cambie deliberadamente un monto o clasificación para crear una discrepancia y trate de emitir un reporte definitivo. Guarde sólo para ese caso. Luego restaure el dato correcto. | La modificación invalida la certificación previa y evita presentar un reporte definitivo aprobado hasta recertificar. Si existe descarga de auditoría, debe distinguirse del reporte definitivo. Restaurar el dato no oculta el historial de cambios. |

En U01, U02 y U09, el segundo revisor debe contrastar los totales y el detalle
contable de los documentos obligatorios, no únicamente aceptar los indicadores
verdes de la pantalla. La muestra de navegación del UAT no reemplaza la
certificación Gold exacta de todas las cuentas exigidas por su manifiesto.

## Cierre del UAT y decisión de lanzamiento

| Control | Estado y referencia de evidencia |
|---|---|
| U01 a U10 ejecutados y revisados | PENDIENTE |
| Incidentes abiertos, gravedad y responsable | PENDIENTE |
| Gold exacto y documentos obligatorios certificados | PENDIENTE |
| Identidad, roles, aislamiento y red aceptados | PENDIENTE |
| TLS, backup, custodia de claves y recuperación supervisada | PENDIENTE |
| Versión y reportes revisados sin modificaciones posteriores | PENDIENTE |
| Firma del analista y segundo revisor | PENDIENTE |
| Firma de seguridad, plataforma y responsable de lanzamiento | PENDIENTE |

Resultado `NO-GO` si hay cuentas/montos/períodos equivocados en el entregable,
doble contabilización, exportación definitiva sin certificación, pérdida de
trazabilidad, acceso no autorizado o un control obligatorio sin ejecutar.
Un incidente cosmético sólo puede aceptarse con responsable y plazo documentados.

`GO` requiere aprobación contable y técnica conjunta sobre la misma versión,
Gold aprobado, controles corporativos completos e incidentes bloqueantes cerrados.
`PILOTO CONTROLADO` requiere acta propia que delimite usuarios, documentos,
ambiente y revisión humana; no autoriza producción general.

Referencia complementaria: [control humano](CONTROL_HUMANO_PREPRODUCCION.md)
y [decisiones corporativas](DECISIONES_CORPORATIVAS_20260908.md).
