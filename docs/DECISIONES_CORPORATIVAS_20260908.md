# Formulario de decisiones corporativas del 8 de septiembre de 2026

Todas las decisiones de este formulario están pendientes. Las opciones son
alternativas para elegir y completar, no configuraciones aprobadas. No incluya
contraseñas, claves privadas, tokens ni cadenas de conexión.

## Identificación y responsables

| Campo | Completar |
|---|---|
| Cliente y organización | |
| Ambiente y versión candidata | |
| Responsable funcional y suplente | |
| Responsable de seguridad y suplente | |
| Responsable de plataforma y suplente | |
| Responsable de continuidad y suplente | |
| Responsable de datos y suplente | |
| Responsable de lanzamiento | |
| Fecha de decisión y revisión | |

## Identidad y permisos

| Decisión | Opciones o información requerida | Elección y aprobador |
|---|---|---|
| Proveedor de identidad | OIDC corporativo existente; Active Directory mediante gateway compatible; nuevo proveedor por definir. Indicar producto, administrador y ambiente de prueba. | PENDIENTE |
| Gateway | Existente o por implementar. Indicar URL HTTPS y ruta de verificación sin credenciales; quién mantiene su disponibilidad. | PENDIENTE |
| Identificador de persona (`actor_id`) | Claim inmutable del proveedor, por ejemplo identificador de sujeto. Escribir nombre exacto, origen y cómo se evita reutilizarlo para otra persona; no asumir que correo o nombre visible son inmutables. | PENDIENTE |
| Organización (`organization_id`) | Claim de organización validado por el gateway, o vínculo fijo del nodo a una organización validado por configuración. Indicar valor de prueba y regla de rechazo si falta o difiere. | PENDIENTE |
| Perfil del nodo | Una organización por instalación; varias organizaciones en una instalación. Si se elige varias, adjuntar pruebas cruzadas con dos identidades y documentos distintos. | PENDIENTE |
| Grupos y roles | Escribir grupo exacto del proveedor para analista, supervisor y administrador. Resolver personas con varios grupos y accesos sin grupo. | PENDIENTE |
| MFA | MFA corporativo para todos; para privilegios elevados con política diferenciada; política pendiente. Especificar mecanismo y excepciones con vencimiento. | PENDIENTE |
| Sesiones | Duración máxima, inactividad, revocación al dar de baja y plazo máximo para que la baja sea efectiva. | PENDIENTE |
| Emergencia | Acceso excepcional administrado por seguridad o sin acceso excepcional. Definir autorización, duración y auditoría si se habilita. | PENDIENTE |

Complete el mapa de permisos y compare con las funciones realmente disponibles.
Un permiso acordado pero todavía no implementado debe quedar bloqueado para el
lanzamiento hasta tener prueba; escribirlo aquí no modifica el software.

| Acción | Roles autorizados propuestos por el cliente | Aprobador | Evidencia de prueba |
|---|---|---|---|
| Cargar y revisar documentos | | | |
| Corregir clasificaciones del caso | | | |
| Emitir reporte definitivo | | | |
| Aprobar promociones al diccionario | | | |
| Gestionar usuarios/configuración | | | |
| Ejecutar backup, restore y rollback | | | |
| Consultar auditoría | | | |

## TLS, red y despliegue

| Decisión | Opciones o información requerida | Elección y aprobador |
|---|---|---|
| Certificado TLS | CA institucional; ACME autorizado por la empresa; CA local de Caddy distribuida por la empresa. Definir nombre de servidor y responsable de renovación. | PENDIENTE |
| Confianza del navegador | Distribución centralizada a equipos; instalación administrada; otro procedimiento documentado. No aceptar ignorar advertencias TLS como método de operación. | PENDIENTE |
| Exposición | Sólo red interna; VPN corporativa; otro acceso sujeto a revisión de seguridad. Indicar puertos y quién verifica reglas efectivas. | PENDIENTE |
| Salida de red | Sin conexión externa; sólo API central HTTPS por destinos autorizados. Listar dominios/puertos, mecanismo de control y responsable. | PENDIENTE |
| Prueba de tráfico | Responsable, herramienta corporativa de observación y evidencia de destinos reales. Incluir tráfico del proxy, no sólo de la aplicación. | PENDIENTE |
| Persistencia | SQLite en nodo único; necesidad de múltiples nodos escritores por evaluar. La evidencia B2 cubre nodo único. | PENDIENTE |
| Imágenes | Registro autorizado, arquitectura, digests, responsable del escaneo y aceptación de vulnerabilidades. | PENDIENTE |

## Claves, respaldo y recuperación

| Decisión | Opciones o información requerida | Elección y aprobador |
|---|---|---|
| Custodia de clave de backup | Gestor corporativo de secretos; custodia externa administrada y documentada; otra solución aprobada. Registrar únicamente referencia lógica, custodios y control de acceso. | PENDIENTE |
| Recuperación de clave | Custodio principal y suplente, procedimiento de recuperación y comprobación de que la clave no depende exclusivamente del servidor respaldado. | PENDIENTE |
| Rotación | Frecuencia, evento de revocación y conservación de claves necesarias para respaldos históricos. | PENDIENTE |
| RPO | Máxima pérdida de datos aceptable, expresada en minutos u horas. Valor: ____; responsable de aceptación: ____. | PENDIENTE |
| RTO | Máximo tiempo aceptable para recuperar operación, expresado en minutos u horas. Valor: ____; responsable de aceptación: ____. | PENDIENTE |
| Programa de respaldos | Frecuencia, ubicación separada, cifrado, retención y alerta si un respaldo no termina. | PENDIENTE |
| Ejercicio supervisado | Fecha, operador, ambiente aislado, lectura y escritura después del restore, tiempos medidos, prueba de rollback y aprobador. | PENDIENTE |

No confunda la antigüedad de un archivo de backup con el RPO observado: debe
registrarse qué datos recuperables se conservaron respecto del momento de la
interrupción. B2 verificó recuperación técnica; no decidió esos objetivos
contractuales ni la custodia definitiva de claves.

## Datos, retención y telemetría

| Tipo de dato | Plazo de retención elegido | Ubicación y acceso | Eliminación/conservación y responsable |
|---|---|---|---|
| Documentos originales y extracción | | | |
| Reportes y decisiones contables | | | |
| Auditoría de operaciones | | | |
| Archivos temporales y cuarentena | | | |
| Respaldos y claves históricas asociadas | | | |
| Metadatos de uso autorizados | | | |

Telemetría: elegir `DESACTIVADA` o `ACTIVADA CON LISTA APROBADA` y registrar
la elección: __________. Si se activa, completar cada campo permitido con
nombre, finalidad, frecuencia, destino, retención y responsable. Sólo habilitar
campos compatibles con el contrato técnico vigente. Este formulario no
autoriza incorporar campos nuevos al software.

Documentos, RUT, nombres o números de cuentas, montos y credenciales permanecen
prohibidos en el canal central según el alcance on-premise del proyecto. Si
una necesidad del cliente entra en conflicto con ese límite, registrarla como
solicitud de cambio pendiente, sin habilitarla durante el ensayo.

## Aceptación

| Entregable | Responsable | Fecha | Evidencia | Estado |
|---|---|---|---|---|
| Identidad y matriz de permisos aprobadas y probadas | | | | PENDIENTE |
| TLS y red verificados en el entorno objetivo | | | | PENDIENTE |
| Claves, backup y recuperación supervisada aprobados | | | | PENDIENTE |
| Retención y telemetría aprobadas | | | | PENDIENTE |
| Riesgos residuales con dueño y vencimiento | | | | PENDIENTE |
| Firma conjunta de seguridad, plataforma y dueño de datos | | | | PENDIENTE |

Una opción pendiente de decidir o de implementar no se convierte en aprobada
por firmar otra sección. Entregue este formulario y las evidencias al responsable
de lanzamiento junto al [UAT](UAT_PREPRODUCTIVO_20260908.md). El acta GO/NO-GO
requiere además Gold y los controles de
[preproducción](CONTROL_HUMANO_PREPRODUCCION.md).
