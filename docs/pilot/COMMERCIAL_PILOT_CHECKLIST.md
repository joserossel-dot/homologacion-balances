# Checklist de ejecución del piloto comercial controlado

Esta checklist se completa fuera de Git y sólo con IDs opacos. Es una guía
operativa propuesta. No reemplaza el protocolo interno, una política de
retención, una autorización contractual ni la evidencia de los controles.

## A. Autorización de la tanda

- [ ] El responsable del piloto aprobó alcance, cliente opaco, equipo y número
      máximo de documentos.
- [ ] Se designaron responsable del piloto, operador, analista, jefatura,
      administrador y custodio de datos, incluso si una persona acumula roles.
- [ ] Existe una decisión externa sobre custodia, acceso, retención y cierre
      de datos para esta tanda.
- [ ] Se confirmó que el servicio se ofrecerá como revisión asistida, sin
      integración automática ni promoción automática al diccionario base.
- [ ] Si intervienen varias personas en un mismo caso, se verificó que el
      flujo no promete edición compartida antes de tener un almacén aprobado.

## B. Versión y entorno

- [ ] Se registraron rama, SHA remoto, fecha, operador y configuración.
- [ ] Existe evidencia de `Release gate` exitoso para el SHA remoto exacto.
- [ ] La prueba local relevante y el control de contrato Excel y JSON
      terminaron correctamente para la versión elegida.
- [ ] Se registró la definición vigente de automática, sugerida, confirmada
      por analista y pendiente.
- [ ] `PILOT_MODE=1` está confirmado antes de abrir la aplicación.
- [ ] `PILOT_TMPDIR` existe, está fuera del repositorio y tiene permisos
      restringidos para el proceso autorizado.
- [ ] Se verificó que el acceso local y el equipo asignado corresponden al
      personal autorizado, cuando se usa `LOCAL_ACCESS_MODE=1`.

## C. Admisión de documentos

- [ ] El manifiesto real permanece fuera de Git y usa IDs opacos.
- [ ] Cada documento tiene SHA-256, tipo, estado autorizado, páginas, período,
      año de cierre y evidencia del año.
- [ ] El validador de manifiesto aceptó el lote real.
- [ ] No hay documentos inesperados, repetidos, sin autorización o con hash
      distinto.
- [ ] El número de documentos y el cliente cumplen el alcance de la tanda.

## D. Revisión por documento

Para cada `document_id` opaco:

- [ ] Se registraron legibilidad, orientación OCR, formato, extracción,
      cobertura y cuadratura.
- [ ] Se registró el estado de entregabilidad y sus razones.
- [ ] Se revisó el alcance de páginas y período frente al original.
- [ ] El analista cotejó cuentas, importes, columna de origen, naturaleza y
      código final para el alcance comprometido.
- [ ] Las filas pendientes, incompatibles o excluidas tienen una decisión y
      una razón documentada.
- [ ] Las cifras reconstruidas, si existieron, se cotejaron contra el
      original antes de usarse.
- [ ] La cuadratura está certificada o se documentó por qué el documento no
      entrega evidencia para aplicarla.
- [ ] La salida indica ID opaco, SHA de origen, SHA de ejecución, estado de
      revisión y condición de uso.

## E. Aprobación de entrega

- [ ] Jefatura revisó el paquete y confirmó que no hay bloqueo pendiente.
- [ ] El archivo entregado cumple el contrato acordado de Excel o JSON.
- [ ] Se informó separadamente el número de cuentas automáticas, sugeridas,
      confirmadas por analista y pendientes.
- [ ] La salida se entrega como paquete revisado de piloto y no se conecta de
      forma automática a sistemas del cliente.
- [ ] Las propuestas al diccionario de equipo siguen separadas del diccionario
      base y tienen su estado registrado.

## F. Cierre y limpieza

- [ ] Existe un informe externo de cierre con resultados por documento,
      incidentes, reprocesos y decisión final.
- [ ] El custodio verificó la retención, devolución o limpieza acordada de
      originales, exportaciones, paquetes de revisión y temporales.
- [ ] Se registró la limpieza de `PILOT_TMPDIR` o una excepción justificada.
- [ ] No quedan datos reales de cliente en Git, reportes versionados o rutas
      no autorizadas.
- [ ] El responsable del piloto decide, con evidencia, si se amplía, mantiene,
      corrige o cierra el piloto.
