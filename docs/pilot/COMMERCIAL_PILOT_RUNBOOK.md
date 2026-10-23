# Runbook para un piloto comercial controlado

## Estado y propósito de este documento

Este runbook es una propuesta operativa para convertir el piloto interno no
mutativo en una prueba comercial acotada. No modifica
`docs/pilot/PROTOCOL.md`, no autoriza por sí solo un lanzamiento comercial ni
declara cumplimiento legal, contractual o de seguridad. Esos asuntos requieren
evidencia y decisiones de los responsables correspondientes.

Su uso previsto es que el responsable del piloto documente, para cada tanda,
qué controles se ejecutaron, quién tomó cada decisión y por qué un documento
fue entregado, devuelto o detenido. Los identificadores que se registren aquí
y en los informes asociados deben ser opacos. No se deben copiar datos de
clientes, PDFs, montos, RUT, nombres de archivos ni resultados al repositorio.

## 1. Alcance propuesto del primer piloto comercial

La primera oferta debe presentarse como un servicio asistido de homologación,
no como una integración automática ni como una certificación contable
independiente.

Alcance propuesto por tanda:

- Un cliente y un equipo de trabajo autorizados.
- Hasta diez documentos autorizados mediante un manifiesto por tanda.
- Documentos PDF o Excel que pasen los controles de legibilidad, formato y
  extracción del producto.
- Entrega de un paquete de revisión y, sólo después de la aprobación humana
  requerida, una salida homogénea en Excel o JSON.
- Sin integración automática con procesos del cliente, sin promoción
  automática al diccionario base y sin aprendizaje automático a partir de la
  tanda.

Quedan fuera de este alcance:

- Procesamiento desatendido de documentos no autorizados.
- Persistencia compartida de balances o edición entre usuarios desde cuentas
  distintas. La documentación actual indica que las cargas viven en la sesión
  del navegador.
- Uso de la API como canal alternativo durante el piloto.
- Publicación de una asignación de equipo en el diccionario base sin un
  proceso separado y auditado.
- Compromisos sobre retención, privacidad, disponibilidad o niveles de servicio
  que no hayan sido definidos y aprobados fuera de este documento.

## 2. Base existente y decisiones pendientes

La siguiente tabla distingue el control documentado o presente en la versión
de trabajo de la decisión que todavía debe demostrarse para cada tanda
comercial. La existencia de una función o de una prueba no sustituye la
evidencia de que se ejecutó sobre el commit y el entorno elegidos.

| Área | Base existente documentada o implementada | Evidencia o decisión pendiente antes de operar comercialmente |
| --- | --- | --- |
| Aislamiento del piloto | El protocolo interno define `PILOT_MODE=1`, un directorio `PILOT_TMPDIR` restringido, Streamlit como punto de entrada y un modo no mutativo. | Registrar el valor efectivo de las variables, los permisos del directorio temporal, el responsable del entorno y el resultado de la limpieza. |
| Autorización de documentos | Existe un manifiesto con IDs opacos, SHA-256, páginas y año de cierre; el protocolo describe un validador previo. | Generar y validar el manifiesto real fuera de Git, y conservar la evidencia externa del resultado. |
| Diagnóstico del documento | El contrato de entregabilidad distingue legibilidad, orientación OCR, formato, extracción, cobertura y cuadratura. | Conservar el diagnóstico por documento y definir quién acepta la causa de un bloqueo o reproceso. |
| Clasificación | El producto separa clasificaciones automáticas, sugeridas y confirmadas por analista. El diccionario de equipo es una superposición privada. | Definir la métrica comercial exacta y no llamar automática a una fila que requirió una decisión individual humana. |
| Revisión contable | El protocolo interno exige revisión del 100% de cuentas, importes, origen, clasificación y cuadratura antes de una salida final. | Mantener ese criterio en el primer piloto comercial, o aprobar explícitamente una política distinta con sus controles y evidencia. |
| Exportación | Las salidas del piloto se identifican como provisionales y no se integran automáticamente. | Demostrar el contrato de salida elegido: contenido, campos obligatorios, valores materializados, trazabilidad y consumo por el receptor. |
| Accesos y diccionario | Existen roles locales y una política de equipo con trazabilidad para propuestas privadas. | Verificar altas, bajas, equipo y roles en el entorno usado. Para colaboración entre usuarios, implementar antes un almacén de trabajo compartido con auditoría. |
| Calidad de la versión | Existe un flujo llamado `Release gate` que instala dependencias, ejecuta pruebas, verifica configuración y realiza un preflight. | Conservar el enlace o evidencia de una ejecución exitosa contra el SHA remoto exacto que procesará la tanda. |
| Datos y retención | El protocolo interno exige almacenamiento externo restringido y limpieza de temporales. | Acordar y registrar fuera de Git el custodio, ubicación, permisos, plazo de retención, devolución o eliminación y manejo de incidentes. |

## 3. Puertas de decisión

Ninguna puerta se salta por una señal favorable de otra. Por ejemplo, una
cuadratura de cero no convierte una extracción no validada en una entrega.

### Puerta A: autorización comercial y operativa

El responsable del piloto debe tener, antes de aceptar un documento:

1. El alcance de la tanda, el contacto operativo, el equipo autorizado y el
   responsable de cierre.
2. Una definición aprobada fuera de Git de custodia, retención, devolución o
   eliminación de datos. Este runbook no define esos términos.
3. La decisión explícita de que el servicio es asistido, que la salida no se
   integrará automáticamente y que el analista conserva la responsabilidad de
   revisar la salida antes de su uso.
4. La confirmación de si el trabajo será de una sola persona por caso. Si habrá
   más de un usuario por caso, el piloto no debe prometer edición compartida
   hasta que exista el almacén de trabajo y la auditoría descritos en
   `docs/pilot/ROLES.md`.

Si falta cualquiera de estos puntos, la tanda no se inicia.

### Puerta B: versión y entorno de ejecución

Antes de abrir Streamlit, el operador debe registrar de forma externa:

1. Rama, SHA remoto, fecha, responsable y configuración aprobada.
2. Evidencia de que el `Release gate` correspondiente al SHA remoto terminó
   correctamente. Una suite local verde o un SHA distinto no sustituyen esta
   evidencia.
3. Resultado de la prueba del contrato de entrega de Excel y JSON, incluidos
   los campos de trazabilidad que recibirá el cliente.
4. Estado limpio o una lista aprobada de cambios no publicados. No se debe
   cambiar código, diccionario base ni configuración a mitad de tanda.
5. `PILOT_MODE=1`, `PILOT_TMPDIR` existente, externo al repositorio y con
   permisos restringidos, además del modo local de acceso cuando corresponda.

Si el entorno no puede demostrarse, se detiene toda la tanda.

### Puerta C: admisión del lote

Para cada documento, el custodio y el operador deben:

1. Crear el manifiesto real fuera de Git a partir de
   `docs/pilot/manifest.example.json`.
2. Usar un `document_id` opaco, SHA-256, tipo de archivo, páginas autorizadas,
   período y año de cierre respaldado por evidencia visible.
3. Ejecutar el validador del manifiesto contra el lote real y conservar la
   salida externa que confirme o rechace el lote.
4. Rechazar documentos faltantes, inesperados, repetidos, no autorizados o
   con un hash distinto.

No se corrige un manifiesto dentro de la aplicación. Un cambio de archivo,
páginas, período, año o SHA exige una nueva autorización.

### Puerta D: ejecución y diagnóstico por documento

El operador registra el resultado de las señales separadas que entrega el
producto:

- Legibilidad y respaldo de orientación OCR.
- Familia o reconocimiento de formato.
- Certificación de extracción y sus motivos.
- Cobertura por cuentas e importe.
- Cuadratura homologada y diferencia, si existe.
- Número de decisiones automáticas, sugeridas, confirmadas por analista,
  incompatibles y pendientes.

Los siguientes estados no pueden avanzar a una salida para el cliente:
`NO_LEGIBLE`, `LECTURA_NO_RESPALDADA`, `EXTRACCION_NO_VALIDADA`,
`FORMATO_NO_SOPORTADO` y `COBERTURA_INSUFICIENTE`.

`REVISION_EXTRACCION_REQUERIDA` sólo puede producir un paquete de cotejo. No
autoriza tratar las cifras reconstruidas como vaciado aprobado hasta que el
analista las coteje con el original.

### Puerta E: revisión, aprobación y entrega

Para el primer piloto comercial se propone conservar la revisión del 100% que
establece el protocolo interno. El analista compara cada cuenta relevante con
el original y registra, como mínimo, nombre, importe, columna de origen,
naturaleza efectiva, código final y motivo de cualquier corrección.

La jefatura aprueba una salida únicamente cuando el registro por documento
demuestre:

1. Extracción apta para revisión según el estado de entregabilidad.
2. Cuadratura certificada y sin diferencia no explicada, cuando el formato
   entregue información suficiente para aplicar ese control.
3. Ninguna cuenta pendiente, incompatible o excluida sin una decisión
   documentada.
4. Revisión del analista completa para el alcance comprometido.
5. Paquete de entrega identificado con ID opaco, SHA de origen, versión o SHA
   de ejecución, estado de revisión y condición de uso.

Una salida `LISTO_PARA_REVISION_ANALISTA` es un paquete de revisión. Una
salida `LISTO_PARA_INTEGRAR` no autoriza una integración automática dentro de
este piloto, porque esa integración sigue fuera de alcance.

### Puerta F: cierre de tanda

El responsable del piloto cierra una tanda sólo después de que el custodio
verifique la retención o limpieza acordada y exista un informe externo con
IDs opacos. El informe debe separar:

- Documentos entregados, reprocesados, rechazados y fuera de alcance.
- Estado de extracción, formato, cuadratura, cobertura y decisión final por
  documento.
- Decisiones del analista, propuestas privadas de diccionario y si quedaron
  activas, revocadas o pendientes de revisión administrativa.
- Incidentes, detenciones, causa, responsable y acción posterior.
- Métricas agregadas de automatización y de intervención humana, sin inflar
  una con la otra.

El cierre de una tanda no incorpora conocimientos al diccionario base ni
autoriza otra tanda sin una nueva admisión.

## 4. Roles durante el piloto comercial

La siguiente asignación reutiliza los roles definidos en `docs/pilot/ROLES.md`.
La aplicación de permisos debe basarse en identidad y `team_id` confiables,
no sólo en elementos visibles de la interfaz.

| Rol | Tarea operativa dentro del piloto | Límite relevante |
| --- | --- | --- |
| Ingreso de datos | Carga los documentos autorizados en su propia sesión y avisa al operador cuando el lote está disponible. | No clasifica, no revisa, no aprueba y no cambia el diccionario. |
| Analista | Coteja la extracción, decide clasificaciones pendientes, documenta excepciones y prepara el paquete de revisión. | No activa ni revoca una asignación privada ni aprueba la entrega final. |
| Jefatura | Revisa la integridad del paquete, aprueba o devuelve entregas del equipo y administra el ciclo de asignaciones privadas dentro de su equipo. | No cruza equipos ni modifica el diccionario base. No puede editar una carga de otro usuario mientras no exista un caso compartido. |
| Administrador | Da acceso, asigna equipos y roles, y evalúa propuestas de incorporación al diccionario base en un proceso separado. | No debe borrar el historial de auditoría ni convertir una aprobación administrativa en una incorporación automática. |
| Responsable del piloto | Autoriza la tanda, versión, manifiesto, excepciones, detenciones y cierre. | No sustituye la revisión contable del analista sin dejar constancia de la excepción. |
| Custodio de datos | Controla originales, temporales, paquetes de revisión, exportaciones, acceso y limpieza externa. | No incorpora datos del cliente al repositorio ni a informes versionados. |

## 5. Métricas que deben acompañar la oferta

El objetivo de producto puede expresarse como al menos 60% de cuentas
automáticas o sugeridas para una revisión asistida. Antes de usar ese número
en una oferta, el responsable debe fijar por escrito la definición aplicada a
la versión ejecutada.

La medición propuesta separa cuatro grupos:

| Grupo | Definición operativa propuesta | Debe contarse como automático |
| --- | --- | --- |
| Automática | Código compatible asignado sin una decisión individual humana en esta tanda. | Sí. |
| Sugerida | Código compatible propuesto, todavía pendiente de confirmación del analista. | No. Debe informarse por separado y puede aportar a la cobertura de revisión asistida si la política aprobada lo permite. |
| Confirmada por analista | Código final decidido o corregido por una persona. | No. |
| Pendiente, incompatible o excluida | Fila que aún necesita decisión, corrección, explicación o exclusión aprobada. | No. |

También se deben informar por separado la cobertura de cuentas y la cobertura
monetaria. Un importe alto no reemplaza la revisión de muchas cuentas, y una
alta cobertura de clasificación no compensa una extracción o cuadratura no
validada.

La regla de umbral, los métodos incluidos y el tratamiento de una propagación
por regla deben quedar en el informe de versión. Hasta que esa definición sea
aprobada, no se debe afirmar un porcentaje comercial como si fuera una tasa de
automatización totalmente comparable entre tandas.

## 6. Incidentes, reproceso y cancelación

### Incidente de documento

Se detiene un documento, se conserva sólo la evidencia autorizada y se abre un
registro externo cuando haya hash distinto, páginas o período no respaldados,
formato no soportado, extracción no validada, una diferencia no explicada o
una clasificación que el analista no pueda justificar.

El resultado permitido es reprocesar con una nueva admisión, solicitar una
fuente distinta, devolverlo como no procesable o declararlo fuera de alcance.

### Incidente de tanda

Se detienen todos los documentos pendientes cuando falte evidencia del modo
piloto, cambie el SHA o configuración, el directorio temporal no cumpla los
controles requeridos, se observe una escritura no autorizada o aparezcan datos
reales en Git o en otro repositorio no aprobado.

La reanudación requiere: causa documentada, corrección verificable, nueva
autorización del responsable y, cuando corresponda, un nuevo manifiesto.

### Cancelación

La cancelación debe producir un informe externo mínimo con IDs opacos, alcance
cancelado, documentos afectados, datos retenidos o eliminados conforme al
acuerdo aplicable, y tareas pendientes. Este documento no prescribe el plazo
ni el método de eliminación.

## 7. Criterio para declarar el piloto comercial apto para ampliación

No se propone declarar éxito sólo porque un documento cuadró. La decisión de
ampliar el piloto debe revisar por lo menos una tanda cerrada con evidencia de:

1. Ejecución sobre un SHA remoto con `Release gate` exitoso.
2. Manifiesto, almacenamiento temporal y limpieza manejados sin incidentes no
   resueltos.
3. Diagnóstico y salida reproducibles por documento.
4. Contrato Excel y JSON validado por el receptor, incluido el tratamiento de
   valores y metadatos.
5. Revisión humana completa y trazable en la primera tanda comercial.
6. Cobertura de clasificación reportada sin mezclar automático, sugerido y
   confirmado manualmente.
7. Cuadratura certificada cuando el documento permita aplicarla; cuando no la
   permita, una explicación explícita de la limitación y del tratamiento
   acordado.
8. Ninguna integración automática, promoción de diccionario base ni caso
   multiusuario presentado como disponible sin el control correspondiente.

Los resultados de esa evaluación pueden conducir a ampliar, mantener el mismo
alcance, corregir el producto o cerrar el piloto. La decisión debe quedar fuera
del repositorio y asociada a evidencia verificable.

## 8. Orden recomendado de trabajo

1. Cerrar el contrato de salida de Excel y JSON, incluyendo valores, campos
   obligatorios y trazabilidad.
2. Ejecutar pruebas locales y `Release gate` contra el SHA remoto elegido.
3. Configurar custodia, acceso y retención para una sola tanda controlada.
4. Ejecutar una tanda de hasta diez documentos con manifiesto y revisión del
   100%.
5. Preparar el informe de cierre y medir el tiempo del analista, cobertura,
   reprocesos y causas de bloqueo.
6. Sólo después de revisar esos resultados, decidir si se construye el almacén
   compartido por equipo, una integración de cliente o una política de revisión
   por muestreo.

La checklist asociada está en
`docs/pilot/COMMERCIAL_PILOT_CHECKLIST.md`.
