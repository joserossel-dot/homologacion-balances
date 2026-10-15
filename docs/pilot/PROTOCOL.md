# Protocolo de piloto interno no mutativo

## 1. Propósito y alcance

Este protocolo regula un piloto interno de homologación de balances con un
solo cliente y un máximo de diez documentos previamente autorizados. Su
objetivo es comprobar el flujo de lectura, extracción, clasificación,
cuadratura y revisión analista bajo condiciones controladas.

No autoriza una operación productiva, el aprendizaje automático, promociones
de conocimiento, cambios al diccionario ni integración automática de un
resultado con los procesos del cliente.

El piloto se ejecuta con `PILOT_MODE=1`. La evidencia automatizada actual
cubre las siguientes protecciones de aplicación:

- Las funciones de persistencia de validaciones, validaciones en lote y
  catálogo no instancian Neon en modo piloto.
- Las decisiones de la sesión se conservan en el estado de sesión de la
  aplicación.
- El diccionario operativo puede leerse para usar el conocimiento vigente,
  pero no se modifica desde el piloto.
- El registro shadow, la gestión de aprendizaje, promociones, rechazos y
  rollbacks se deshabilitan en la interfaz durante el piloto.
- El único punto de entrada autorizado es Streamlit. La API FastAPI se
  deshabilita explícitamente durante el piloto antes de inicializar su
  repositorio o leer archivos cargados.

Estas pruebas no demuestran por sí solas que el navegador, el sistema
operativo, un proxy, la plataforma de ejecución o un servicio externo no
generen registros. El responsable operativo debe aplicar los controles de
almacenamiento y acceso definidos en este documento.

## 2. Roles y separación de responsabilidades

| Rol | Responsabilidad mínima |
| --- | --- |
| Responsable del piloto | Autoriza el cliente, los documentos, el commit de ejecución y el cierre. Detiene el piloto ante una condición de parada. |
| Operador | Verifica el manifiesto, activa `PILOT_MODE=1`, ejecuta los documentos autorizados y registra evidencias sin incorporar datos de cliente al repositorio. |
| Analista contable | Revisa el 100% de las cuentas, cifras, clasificación y cuadratura de cada documento que avance a revisión. No aprueba una exportación final por una señal automática aislada. |
| Custodio de datos | Mantiene los originales, paquetes de revisión y exportaciones temporales fuera del repositorio, en almacenamiento externo restringido. |

Una misma persona puede desempeñar más de un rol sólo si el responsable del
piloto deja constancia de la excepción en el informe de cierre.

## 3. Precondiciones antes de aceptar documentos

1. Crear un manifiesto a partir de `docs/pilot/manifest.example.json` fuera
   del repositorio. El manifiesto real no se versiona en Git.
2. Usar un identificador opaco de cliente y un identificador opaco por
   documento. No incluir razón social, RUT, nombre original del archivo,
   números de cuenta, montos ni documentos de cliente en Git, issues, commits
   o reportes versionados.
3. Guardar los originales y cualquier exportación temporal exclusivamente en
   almacenamiento externo restringido. El manifiesto sólo puede conservar una
   referencia opaca a ese objeto.
4. Calcular y registrar SHA-256 de cada archivo antes de procesarlo. Un hash
   distinto al manifiesto bloquea ese documento hasta que se genere un nuevo
   manifiesto autorizado.
5. Registrar el año de cierre confirmado por documento y la evidencia que lo
   respalda, por ejemplo la cabecera visible del balance. El operador no debe
   deducirlo del nombre del archivo. Si el año no puede confirmarse, las
   reglas dependientes del período permanecen en revisión.
6. Registrar el commit, rama, fecha y responsable de la ejecución. No cambiar
   el código, el diccionario ni la configuración durante una misma tanda del
   piloto.
7. Confirmar que hay como máximo diez documentos con estado `AUTHORIZED` y
   que todos pertenecen al único cliente autorizado.
8. Confirmar `PILOT_MODE=1` antes de abrir la aplicación. Si no puede
   demostrarse ese valor en la sesión, no se procesan documentos.
9. El custodio debe preparar antes de abrir la aplicación un directorio
   temporal exclusivo, existente y fuera del repositorio. Debe pertenecer al
   entorno controlado del piloto, permitir escritura al proceso operador y no
   conceder acceso a grupo ni a otros usuarios (`0700` o una configuración más
   restrictiva que mantenga la escritura necesaria). El operador lo entrega
   mediante `PILOT_TMPDIR`; la aplicación bloquea el inicio si falta, no es un
   directorio, está dentro del repositorio o sus permisos no son restringidos.
   La aplicación no crea este directorio.

### Prechequeo reproducible del manifiesto

Antes de abrir la aplicación, el operador ejecuta el validador contra el
manifiesto y el lote externo autorizado. El archivo de lote es un objeto JSON
`document_id_opaco -> ruta_local`; ambas rutas se mantienen fuera del
repositorio. Por ejemplo:

```bash
python scripts/validate_pilot_manifest.py \
  --manifest /almacenamiento-restringido/manifiesto-piloto.json \
  --batch /almacenamiento-restringido/lote-autorizado.json
```

El comando compara los bytes reales con cada SHA-256 autorizado, rechaza
documentos faltantes, inesperados, duplicados o no autorizados, y exige un
único cliente y un máximo de diez documentos. Sólo un resultado con salida
`valid: true` permite continuar. Su salida no incluye rutas locales, hashes ni
contenido de los documentos.

### Arranque controlado

Una vez preparado por el custodio el directorio temporal restringido, el
operador inicia exclusivamente la aplicación Streamlit con ambos controles:

```bash
PILOT_MODE=1 PILOT_TMPDIR=/almacenamiento-restringido/tmp-piloto \
  poetry run streamlit run app_validacion.py
```

La API FastAPI no forma parte del piloto y responderá como no disponible si
recibe `PILOT_MODE=1`. No debe iniciarse como alternativa al comando anterior.

## 4. Ejecución por documento

1. El operador verifica identidad opaca, SHA-256 y páginas seleccionadas
   contra el manifiesto.
2. El operador procesa sólo las páginas y el período indicados, incluido el
   año de cierre confirmado en el manifiesto. Cuando la
   aplicación sugiera alcance por período, la selección continúa siendo una
   decisión explícita del analista.
3. Se conserva el diagnóstico de legibilidad, formato, extracción, controles
   de origen, cuadratura homologada, cobertura de clasificación y estado de
   entrega.
4. El analista revisa el 100% de las cuentas del documento, incluidas las
   automáticas y las sugeridas. La revisión debe contrastar nombre, importe,
   columna de origen, naturaleza efectiva, código elegido y el PDF o Excel
   original.
5. Las decisiones tomadas durante la sesión se documentan en el paquete de
   revisión externo. No se promueven al diccionario, Gold Standard, runtime ni
   a una base de conocimiento desde el piloto.
6. Toda exportación queda marcada como `PILOTO`, con identificador opaco,
   SHA-256 de origen, commit de ejecución y resultado de la revisión. No se
   integra automáticamente a procesos del cliente.
7. La extracción puede generar temporales técnicos inevitables, por ejemplo
   copias PDF o PNG de OCR. En modo piloto deben quedar exclusivamente bajo el
   directorio preaprobado en `PILOT_TMPDIR`; no son escritura persistente ni
   autorización para escribir originales, resultados, reportes o datos de
   cliente en el repositorio.

## 5. Estados de decisión

La aplicación puede producir los siguientes estados. El protocolo define qué
puede hacerse con cada uno; ninguno reemplaza la revisión completa del
analista.

| Estado | Tratamiento dentro del piloto |
| --- | --- |
| `NO_LEGIBLE` | Detener el documento. Solicitar una fuente legible o registrar el rechazo. |
| `LECTURA_NO_RESPALDADA` | Detener el documento. No usar cifras ni clasificaciones como resultado revisable. |
| `EXTRACCION_NO_VALIDADA` | Detener el documento para integración. Puede conservarse como evidencia de fallo de extracción. |
| `REVISION_EXTRACCION_REQUERIDA` | Permitir sólo un paquete de cotejo contra el original. No emitir exportación definitiva ni integrar. |
| `FORMATO_NO_SOPORTADO` | Detener el documento. Registrar el formato como no soportado sin incorporar el archivo a aprendizaje. |
| `COBERTURA_INSUFICIENTE` | Mantener en revisión. No tratar la cobertura como automatización suficiente para una entrega. |
| `LISTO_PARA_REVISION_ANALISTA` | Permitir revisión analista completa y una exportación provisional identificada como piloto. No integrar sin la decisión posterior del analista. |
| `LISTO_PARA_INTEGRAR` | Permitir preparar la salida revisada sólo después de la revisión del 100% de las cuentas. La integración efectiva sigue fuera del alcance de este piloto. |

La cuadratura cero no compensa una extracción no validada, un formato no
soportado ni una cuenta pendiente de decisión. Del mismo modo, una
clasificación automática no elimina la obligación de revisión del piloto.

## 6. Condiciones de parada

### Parada de documento

Detener el documento cuando ocurra cualquiera de estas situaciones:

- El hash no coincide con el manifiesto, el archivo no está autorizado o se
  excede el máximo de diez documentos.
- El estado es `NO_LEGIBLE`, `LECTURA_NO_RESPALDADA`,
  `EXTRACCION_NO_VALIDADA` o `FORMATO_NO_SOPORTADO`.
- No se puede verificar la selección de páginas o período frente al original.
- El analista detecta una cifra, clasificación, columna de origen o cuadratura
  que no puede justificar con evidencia del documento.

### Parada completa del piloto

Detener todos los documentos pendientes y escalar al responsable cuando:

- No se puede demostrar `PILOT_MODE=1` en la sesión de ejecución.
- Falta `PILOT_TMPDIR`, no cumple las restricciones de acceso, se detecta un
  temporal del piloto fuera de ese directorio o quedan residuos temporales al
  cierre de una sesión sin una justificación y limpieza registrada.
- Se detecta una escritura persistente fuera de los temporales técnicos
  autorizados, una promoción, aprendizaje, rollback o cambio de diccionario
  atribuible a la sesión de piloto.
- Cambia el commit, la rama, la configuración o el manifiesto sin una nueva
  autorización documentada.
- Un original, una exportación con datos reales o un identificador real de
  cliente aparece en Git, en un reporte versionado o fuera del almacenamiento
  externo restringido aprobado.
- No existe analista disponible para la revisión del 100% de las cuentas.

La reanudación exige documentar la causa, corregir la condición y obtener una
nueva autorización del responsable del piloto.

## 7. Cierre y reporte

Al terminar la tanda, el responsable genera un informe externo de cierre que
use sólo identificadores opacos y contenga, por documento:

- SHA-256, tipo de archivo, páginas, período procesado y año de cierre
  confirmado con su evidencia.
- Commit, rama, fecha de ejecución y versión del manifiesto.
- Estado de entrega, diagnóstico de extracción, formato y resultado de
  cuadratura.
- Número de cuentas, cobertura automática o sugerida, número de cuentas
  revisadas y resultado de la revisión del analista.
- Decisión de cierre: `APROBADO_PARA_EVALUACION_POSTERIOR`,
  `REQUIERE_REPROCESO`, `RECHAZADO_POR_EVIDENCIA` o `FUERA_DE_ALCANCE`.
- Incidentes, condiciones de parada y acciones pendientes.

El informe no activa aprendizaje ni cambia reglas. Cualquier mejora posterior
debe tratarse en una actividad separada, con datos autorizados, pruebas y una
revisión de publicación independiente.

## 8. Retención y limpieza

El custodio de datos aplica el plazo de retención acordado con el cliente y
elimina o devuelve originales, paquetes temporales y exportaciones desde el
almacenamiento externo restringido al cerrar el piloto. Antes de cerrar cada
sesión, verifica y limpia el directorio definido por `PILOT_TMPDIR`; cualquier
residuo se trata como incidente y activa la condición de parada hasta dejar
constancia de su limpieza. Esta limpieza se registra fuera de Git con
identificadores opacos, fecha, responsable y alcance de eliminación.

El repositorio debe conservar únicamente este protocolo, el ejemplo de
manifiesto y evidencias técnicas sin datos reales de cliente.
