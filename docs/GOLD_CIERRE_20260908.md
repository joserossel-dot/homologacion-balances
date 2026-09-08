# Estado de cierre Gold, 8 de septiembre de 2026

## Alcance y evidencia

Ejecución local final sobre el commit funcional
`ea51045`. No constituye aprobación de producción.

Evidencias conservadas fuera del repositorio:

- `private-release-final-shared-20260908.json`: matriz documental básica posterior a la corrección conservadora de prefijos jerárquicos.
- `gold-final-shared-20260908.json`: comparación exacta contra los Gold privados vigentes.
- Ejecución focal privada: 119 pruebas aprobadas, ninguna omitida ni fallida,
  en 72,40 segundos. Los 17 casos antes omitidos se activaron usando los
  recursos privados reales mediante rutas configuradas en memoria, sin
  copiarlos al repositorio. Este resultado proviene de pytest, no de los dos
  informes JSON.

Los recursos privados utilizados conservaron sus hashes antes y después. No se modificaron expectativas Gold ni se realizaron commit, push o escrituras en Neon en este frente.

## Matriz básica: 4/4 expectativas cumplidas

| Caso | Estado técnico | Cumple su manifest |
|---|---|---|
| Parque Cultural | Certificada | Sí |
| London | Certificada | Sí |
| Afuminsal | Certificada | Sí |
| Fundación Arte y Solidaridad | Parcial | Sí, el control exige este estado |

El 4/4 no significa cuatro documentos certificados ni cierre de todas las revisiones humanas. En Afuminsal la certificación conserva la advertencia de movimientos cerrados de Debe/Haber no reproducidos por el detalle impreso; las columnas finales y el cierre sí satisfacen el control aplicado. Fundación conserva revisión de evidencia reconstruida.

## Gold exacto: 0/3

| Caso | Certificación técnica | Filas discrepantes | Campos discrepantes |
|---|---|---:|---|
| ABS | Parcial | 37 | Método: 23; confianza: 37 |
| Cosemar | Certificada | 32 | Método: 32 |
| Purefruit | Certificada | 28 | Método: 28; código: 1 |

Son 97 filas únicas con diferencias de método y/o confianza. Hay 83 diferencias de método y 37 de confianza; estos conteos se superponen y no deben sumarse como filas independientes. Una de esas mismas filas contiene además la única diferencia de código.

Los controles de filas faltantes y adicionales no registran diferencias. La comparación no reporta diferencias monetarias. Esto no sustituye la revisión de procedencia ni permite omitir las discrepancias restantes.

ABS permanece parcial por evidencia de extracción pendiente de revisión, un control de resultado duplicado y controles/secciones no acreditados para el alcance evaluado. Actualizar metadatos esperados por sí solo no resuelve ese bloqueo.

La única diferencia de código es `PNC.05` actual frente a `PNC.01` en el Gold para «Otros pasivos financieros no corrientes». La coordinación de integración identifica esta etiqueta como ya aprobada globalmente. Los informes JSON demuestran la diferencia, pero no contienen por sí mismos el registro de esa aprobación.

## Procedimiento propuesto para actualizar expectativas

1. Vincular la aprobación global de la etiqueta con su registro verificable: responsable, fecha, alcance, código vigente y versión del catálogo. Si falta ese registro, solicitarlo antes de cambiar el Gold.
2. Conservar el Gold histórico y sus hashes. Preparar una nueva versión candidata privada, con un diff explícito limitado a la expectativa de código autorizada. No sobrescribir la referencia histórica.
3. Revisar separadamente cada cambio de método y confianza. Documentar si representa un cambio técnico esperado o evidencia pendiente. No copiar automáticamente la salida actual a las expectativas para obtener un resultado verde.
4. Resolver la evidencia pendiente de ABS mediante revisión contra el documento y el flujo de recertificación aplicable, sin rebajar el estado requerido ni eliminar controles para aprobarlo.
5. Registrar autor, revisor, motivo, hashes anterior/nuevo y diferencias aprobadas. Actualizar la referencia del manifest sólo con autorización explícita y conservar trazabilidad de la versión previa.
6. Reejecutar la matriz Gold exacta y las regresiones afectadas. Comunicar por separado certificación técnica, coincidencia Gold y autorización de lanzamiento.

## Pendientes de cierre

- Formalizar la trazabilidad de la aprobación global y resolver la expectativa antigua de código por el procedimiento anterior.
- Revisar y aprobar, o corregir técnicamente, las diferencias de método/confianza.
- Completar la revisión de evidencia y controles de ABS.
- Obtener una nueva ejecución Gold satisfactoria antes de considerar cerrado este frente. La matriz básica y las 119 pruebas privadas no reemplazan este requisito ni los restantes controles de producción.
