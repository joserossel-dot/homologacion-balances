# Hoja de ruta de lanzamiento on-premise

## Objetivo

Convertir el candidato funcional actual en un producto on-premise protegido.
El procesamiento de documentos, OCR, clasificación, revisión, reportes y datos
contables permanece en la infraestructura del cliente. La nube actúa sólo como
plano de control para licencias, paquetes maestros firmados y telemetría mínima.

## Reglas de ejecución

Coordinación externa propuesta el 2026-09-07:
[Plan con Google Antigravity](PLAN_COLABORACION_ANTIGRAVITY.md). El primer
encargo es una auditoría de solo lectura. La implementación externa requiere
una base aislada que incluya los cambios locales y propiedad explícita de
archivos. Preparar el plan no inicia agentes externos ni autoriza publicación.

- Ninguna fase se considera terminada sólo porque el código compile.
- Cada punto debe tener evidencia reproducible y responsable identificado.
- No se procesarán datos reales en ambientes públicos sin autenticación.
- Los cambios pasan por candidato limpio, pruebas completas y recertificación
  Gold antes de publicarse.
- Los documentos privados y libros Gold no se incorporan a Git.
- Un hallazgo crítico bloquea el entregable definitivo.

## Repriorización por auditoría del 30 de agosto de 2026

Se congelan nuevas familias ERP y funciones experimentales hasta cerrar los
siguientes controles. La revisión Gold continúa bloqueada para no validar
libros con métricas o alertas de extracción incompletas.

### P0 automatizable

1. Separar clasificación específica, residual, no clasificada, pendiente y
   controles en pipeline, métricas, reportes y certificación.
2. Retirar `src/db_repository.py` y todo uso de TLS sin verificación, migrando o
   eliminando coherentemente sus consumidores.
3. Detectar líneas fusionadas o anómalas antes de clasificar y prohibirles una
   clasificación automática de alta confianza.
4. Fallar explícitamente cuando OCR requerido no tiene idioma español, termina
   con error o devuelve cero cuentas.
5. Comparar cuadre de extracción con cuadre homologado y bloquear degradaciones
   introducidas por la clasificación.
6. Hacer explícito que una ejecución CI con cero pruebas recolectadas es error.

### P1 automatizable

1. Medir por separado OCR escaneado, balance codificado y presentación IFRS sin
   código, incluyendo la ruta de etiquetas auditadas.
2. Inventariar módulos productivos, shadow, offline, sólo pruebas y huérfanos;
   eliminar únicamente los huérfanos inequívocos.
3. Formalizar la política de promoción del diccionario con aprobación,
   evidencia, conflictos, expiración y rollback.
4. Actualizar README, dependencias OCR y documentación de arquitectura.

### Controles humanos posteriores

1. Revisar Gold schema 2 una vez integrados los controles P0.
2. Elegir proveedor de identidad, claims y responsables de roles.
3. Aprobar telemetría, custodia de claves, CA, RPO, RTO y retención.
4. Aceptar el ciclo Docker en el entorno objetivo; la evaluación técnica real
   quedó aprobada en B2 el 8 de septiembre, con controles humanos pendientes.

## Oleadas paralelas

| Oleada | Frentes paralelos | Dependencias | Control de salida |
|---|---|---|---|
| 1 | Fase 0 Contención, Fase 1 Candidato funcional, Fase 2 Arquitectura | Línea base `c70e60e` | Riesgos inmediatos contenidos, candidato recertificado y arquitectura aprobada |
| 2 | Fase 3 Desacoplamiento, Fase 4 Paquete local, Fase 5 API central | Contratos de Fase 2 | Nodo local funciona sin nube y API no recibe información contable |
| 3 | Fase 6 Seguridad, Fase 7 Certificación integral | Componentes de oleada 2 | Controles técnicos, recuperación y matriz completa aprobados |
| 4 | Fase 8 Piloto controlado | Oleada 3 aprobada | Hallazgos críticos resueltos y aceptación del piloto |
| 5 | Fase 9 Lanzamiento por cliente | Piloto aprobado | Instalación, soporte, respaldo y rollback aceptados |

## Estado general

Actualización vigente: 8 de septiembre de 2026. La evidencia
[B2](../entrega/AUDITORIA_ANTIGRAVITY_B2_0e2625d.md) audita exactamente
`0e2625df513e63263886e54d7cd4edd90dbedb10`; el HEAD publicado
`535ecb1d6410fdfb909dda9228ad2f8a254b4636` incorpora ese informe documental.
Las cifras B2 siguientes pertenecen al candidato auditado. Posteriormente, el
commit funcional `ea51045` corrigió el tratamiento de prefijos jerárquicos y
cerró un falso positivo de ecuaciones de resultados. Sobre ese commit se
recolectaron 1.440 pruebas: 1.423 aprobadas, 17 omitidas y 3 advertencias. Las
17 omisiones fueron activadas por separado con recursos privados externos al
repositorio: 119 aprobadas, ninguna omitida ni fallida. El smoke Docker real
volvió a aprobar sus 8 controles. Gold exacto permanece 0/3, por lo que esta
regresión no cambia el `NO-GO` de producción.

B2 registra 1.418 pruebas recolectadas, 1.401 aprobadas, 17 omitidas y
3 advertencias; verificador on-premise 49/49; smoke Docker real de evaluación
8/8 con salida 0. Se verificaron HTTPS con CA local explícita, persistencia,
backup cifrado, restore y recuperación de salud. Dictamen: aprobado con
observaciones para continuar controles preproductivos; producción sigue NO-GO.
Los cierres diarios anteriores se conservan como historia y no sustituyen
esta actualización del estado Docker.

Estados permitidos: `PENDIENTE`, `EN_CURSO`, `BLOQUEADO`, `EN_REVISION`,
`COMPLETADO`.

| Fase | Estado al 2026-09-08 | Evidencia mínima de cierre |
|---|---|---|
| 0. Contención y línea base | EN_CURSO | Acceso restringido, repositorio y ramas protegidos, 2FA y respaldos verificados |
| 1. Candidato funcional definitivo | BLOQUEADO | Suite completa y Gold exacto sin fallas |
| 2. Arquitectura y contrato de datos | EN_REVISION | ADR y contrato nodo-nube aprobados |
| 3. Desacoplamiento del código | EN_REVISION | Interfaces locales/remotas y operación sin dependencia directa de Neon |
| 4. Paquete on-premise | EN_REVISION | Evaluación Docker real aprobada en B2; faltan aceptación del entorno cliente, red, actualización y rollback operativo |
| 5. API central | PENDIENTE | Licencias, paquetes firmados y telemetría mínima probados |
| 6. Seguridad, identidad y auditoría | EN_REVISION | Autenticación, roles, auditoría, cifrado y pruebas de aislamiento |
| 7. Certificación integral | BLOQUEADO | Matriz funcional, documental, técnica y de seguridad aprobada |
| 8. Piloto controlado | PENDIENTE | Métricas y aceptación sin hallazgos críticos abiertos |
| 9. Lanzamiento productivo | PENDIENTE | Acta de aceptación por cliente y operación soportada |

## Fase 0. Contención y línea base

- [ ] Restringir Render a staging o demostración sin datos reales.
- [ ] Resolver la exposición pública del repositorio y sus datos derivados.
- [ ] Activar 2FA, secret scanning, Dependabot y análisis de código.
- [ ] Proteger `main` y la rama de release.
- [x] Registrar `c70e60e` como línea base histórica; candidato B2 `0e2625d`,
  informe incorporado en HEAD publicado `535ecb1`.
- [ ] Probar respaldo y lectura de catálogo/diccionario Neon.
- [ ] Definir responsable de seguridad y responsable de release.

## Fase 1. Candidato funcional definitivo

- [x] Integrar jerarquía de subtotales sin sumar controles como cuentas.
- [x] Heredar Banco Estado desde el subtotal Bancos.
- [x] Clasificar depreciación acumulada en `ANC.01.01` aunque provenga de Pasivo.
- [x] Mantener separada la depreciación del ejercicio en resultados.
- [x] Compactar sugerencias de revisión.
- [x] Hacer que el certificador use la misma jerarquía que la interfaz.
- [x] Exigir estado de certificación en cada caso obligatorio.
- [ ] Incorporar Parque Cultural como Gold exacto.
- [x] Ejecutar suite completa y corpus privado en un checkout limpio.
- [x] Activar y probar el bloqueo de exportación ante hallazgos críticos.

Estado de revisión: la matriz básica cumple 4/4 expectativas, con 3/3 casos
obligatorios certificados y un caso OCR mantenido como `parcial` para control
humano. El contrato Gold endurecido deja
ABS, Cosemar y Purefruit en 0/3 porque los libros históricos no demuestran aún
la coincidencia exacta de método, confianza, jerarquía y columnas derivadas.
Existen candidatos privados schema 2 para revisión. Parque Cultural también
tiene candidato privado, pero no puede promoverse hasta revisar sus 174 filas y
completar período y moneda. Las rutas de certificación parcial, certificación
obsoleta después de edición manual y confusión entre años históricos, notas y
montos fueron corregidas y cuentan con pruebas; la fase sigue bloqueada hasta
aprobar Gold nuevamente.

## Fase 2. Arquitectura y contrato de datos

- [ ] Aprobar diagrama local, plano central y límites de confianza.
- [ ] Aprobar el perfil de persistencia: B2 verifica SQLite WAL para nodo único;
  evaluar PostgreSQL si se requiere escalamiento distribuido.
- [ ] Definir modo conectado, período de gracia y modo desconectado.
- [ ] Definir autenticación local: OIDC, Active Directory o cuentas administradas.
- [ ] Aprobar campos permitidos y prohibidos en telemetría.
- [ ] Definir compatibilidad entre software, catálogo, reglas y migraciones.
- [ ] Aprobar modelo de amenazas y política de retención.

## Fase 3. Desacoplamiento del código

- [x] Crear interfaces de documentos, ejecuciones, conocimiento, auditoría,
  usuarios y reportes.
- [x] Crear clientes separados de licencias, datos maestros y telemetría.
- [x] Retirar dependencia directa de Neon desde el modo de procesamiento local.
- [x] Encapsular las escrituras JSON y SQLite detrás de repositorios auditados.
- [x] Persistir documento, alcance de páginas, proceso, correcciones y reporte.
- [x] Probar que el modo local no instancia Neon ni depende de la API central.
- [x] Conciliar huérfanos, hashes inválidos y temporales mediante escaneo de sólo
  lectura y cuarentena recuperable, sin borrado definitivo.

## Fase 4. Paquete on-premise

- [x] Crear `docker-compose.yml` para aplicación, persistencia local JSON+SQLite
  y componentes auxiliares. PostgreSQL queda sólo en perfil heredado opcional.
- [x] Ejecutar contenedores sin root.
- [x] Agregar healthchecks, redes internas y límites de recursos.
- [x] Configurar volúmenes persistentes y temporales separados.
- [x] Gestionar secretos y respaldos fuera del contexto y de la imagen.
- [ ] Restringir la salida de red al plano central autorizado.
- [x] Probar instalación, arranque y persistencia en Docker real de evaluación,
  con HTTPS y CA local explícita; B2 registra salida 0 del smoke 8/8.
- [x] Probar backup cifrado, restore runtime, permisos UID/GID 10001 y
  recuperación de salud en Docker real de evaluación, según B2.
- [ ] Aceptar instalación en entorno objetivo, actualización y rollback con
  fallo real; completar custodia de claves y ejercicio operativo con RPO/RTO.

La fase permanece `EN_REVISION`. El subcontrol Docker de evaluación pasa de
bloqueado por daemon a aprobado con observaciones. B2 no cierra identidad,
TLS corporativo, tráfico saliente ni recuperación supervisada por el cliente.

`scientific_validation` no está implementado ni operativo. No forma parte de
ningún gate declarado y no debe presentarse como evidencia de certificación.

## Fase 5. API central

- [ ] Implementar organizaciones, contratos, licencias y nodos autorizados.
- [ ] Emitir licencias locales firmadas con vencimiento y gracia.
- [ ] Distribuir paquetes maestros versionados, firmados y reversibles.
- [ ] Validar compatibilidad antes de aplicar una actualización.
- [ ] Rechazar documentos, RUT, cuentas, montos y conexiones de bases del cliente.
- [ ] Implementar telemetría mínima con retención definida.
- [ ] Registrar acciones administrativas y revocaciones.

## Fase 6. Seguridad, identidad y auditoría

- [x] Implementar roles analista, supervisor y administrador con denegación por
  defecto.
- [x] Identificar al analista, actor, organización y roles en decisiones y
  reportes.
- [x] Probar aislamiento de la persistencia local entre organizaciones.
- [ ] Implementar rotación y revocación de credenciales por nodo.
- [x] Proteger paquetes contra alteración y repetición mediante atestación
  Ed25519 vinculada a commit, manifiestos, documentos y resultados.
- [x] Incorporar escaneo automatizado de código, dependencias y secretos.
- [ ] Definir eliminación segura y conservación de auditoría.
- [ ] Ejecutar prueba de respaldo y restauración con RPO/RTO acordados.

## Fase 7. Certificación integral

- [ ] Cubrir PDF, Excel, OCR, rotación, auditados, dos períodos y monedas.
- [ ] Cubrir páginas seleccionadas, subtotales, contra-activos y notas.
- [ ] Medir exactitud por cuenta, monto, período y cobertura monetaria.
- [ ] Verificar cuadratura e integridad del estado de resultados.
- [ ] Verificar contrato rígido del Excel de integración.
- [ ] Ejecutar pruebas de carga, fallas, seguridad y recuperación.
- [ ] Emitir informe de readiness con bloqueadores residuales.

## Fase 8. Piloto controlado

- [ ] Seleccionar uno o dos clientes y documentos autorizados.
- [ ] Instalar ambientes separados y respaldados.
- [ ] Mantener revisión humana obligatoria.
- [ ] Medir automatización, correcciones, tiempos, fallas e incidentes.
- [ ] Resolver hallazgos críticos y obtener aceptación del piloto.

## Fase 9. Lanzamiento productivo

- [ ] Publicar versión e imágenes firmadas e identificadas por digest.
- [ ] Entregar licencia, configuración, manual y respaldo inicial.
- [ ] Definir soporte, actualización, rollback y responsables.
- [ ] Completar acta de aceptación técnica por cliente.

## Revisión diaria

Al cierre de cada día se actualizará esta tabla y se acompañará con evidencia.

| Fecha | Avances verificados | Pendientes | Bloqueos | Pruebas | Próximo paso |
|---|---|---|---|---|---|
| 2026-08-29 | Séptima oleada integrada: binding de certificación serializable y auditable; paquete privado de revisión Gold; atestación anti-replay; autenticación proxy default deny; imágenes por digest; backup cifrado; restore y rollback simulados | Revisar 97 cuentas Gold; ejecutar build/smoke/restore Docker real; elegir proveedor y claims de identidad; aprobar custodia de claves, CA, digests y RPO/RTO | Gold endurecido 0/3; Docker daemon inactivo; autorización interna y allow-list FQDN requieren arquitectura del cliente; configuración administrativa de GitHub no verificada | Suite 1.069 aprobadas, 17 omitidas; matriz básica 4/4; Gold 0/3 bloqueado; verificador on-prem 19/19; diff limpio | Completar revisión humana Gold y prueba operacional Docker en servidor limpio; repetir recertificación y emitir atestación real sólo después del commit |
| 2026-09-07 | Métricas específicas/residuales separadas; ciclo Streamlit persistente por documento y alcance; reporte definitivo certificado persistido y releído; timeouts OCR aislados; conciliación runtime recuperable; rutas legacy inseguras retiradas; reconciliación OCR degradada a `parcial` cuando el subtotal no prueba el dígito exacto | Confirmar la fila 19 de Fundación; revisar 97 discrepancias Gold; ejecutar smoke Docker real; escoger proveedor de identidad; verificar cola de promociones con vista Neon de sólo lectura; confirmar consumidores externos de cuatro módulos | Gold 0/3; daemon Docker no disponible; backlog Neon no verificable sin vista/credencial; 17 pruebas omitidas por fixtures privados o Gold ausente | 1.202 aprobadas, 17 omitidas y 3 advertencias; 1.219 recolectadas; matriz básica 4/4 expectativas, con 3 obligatorias certificadas y 1 control parcial; Gold 0/3; verificador on-prem 37/37; OCR español disponible; 0 bypass TLS y 0 entrypoints faltantes | Ejecutar el control humano en orden: Fundación, Gold, identidad, Docker, promociones, consumidores externos y acta GO/NO-GO |
| 2026-09-09 | Candidato `bef3da4a823ae21fe8e84a980a0a0562f0a42ee3` publicado; Gold exacto 3/3; matriz privada 4/4 expectativas con 3 obligatorias certificadas y 1 control parcial; atestación Ed25519 ligada al commit y manifiestos; paquete on-premise, reinicio, backup y restore aprobados; Neon y diccionario del pipeline verificados; Render confirmó el mismo commit en estado `live` | Ejecutar piloto autogestionado como empresa; documentar aceptación funcional e incidencias; definir identidad corporativa y claims; confirmar custodia operativa de la clave privada y política de rotación; completar acta GO/NO-GO antes de producción desatendida | Sin bloqueo técnico del gate para iniciar el piloto controlado; producción general permanece bloqueada hasta aceptación humana, identidad por cliente y cierre operativo | Release gate GitHub `34401951448` aprobado: suite completa, contratos privados, CodeQL, auditoría de dependencias, Gitleaks, smoke y recuperación Docker, firma privada, Neon y despliegue exacto | Ejecutar el guion `PILOTO_AUTOGESTIONADO.md` en una instalación limpia, registrar resultados y decidir aceptación, aceptación con incidencias o rechazo |

## Controles cerrados y bloqueadores abiertos

Controles cerrados por las oleadas sexta y séptima:

- La certificación queda vinculada al contenido exacto y caduca ante cualquier
  edición manual de monto, columna u origen.
- Los casos obligatorios rechazan estados `parcial` y `no_evaluable`.
- Los períodos se obtienen de encabezados tabulares relevantes; notas y años
  históricos quedan excluidos como montos o períodos.
- El gate privado valida una atestación Ed25519 reproducible y anti-replay.
- Los bloqueadores duros impiden el reporte definitivo en producción.
- Secretos, respaldos y dumps quedan fuera del contexto Docker y de toda capa
  de imagen.
- Las semillas empaquetadas no sobrescriben decisiones humanas locales.
- La restauración runtime verifica integridad, crea respaldo previo y usa
  staging con rollback local probado. B2 verifica restore y recuperación de
  salud en Docker real de evaluación; rollback ante fallo real y aceptación
  operativa del cliente siguen pendientes.
- La aplicación crea o recupera la ejecución durable después de confirmar
  páginas y períodos, audita correcciones sin montos y sólo persiste un reporte
  definitivo cuando la certificación completa está aprobada.
- Un timeout OCR queda separado de una falla contable, mata el grupo de procesos
  auxiliares, impide crear Gold y permite continuar con otros documentos.
- La conciliación local escanea sin escribir y sólo mueve hallazgos mediante una
  orden explícita a una cuarentena restaurable y aislada por organización.

Bloqueadores que todavía anulan una aprobación de producción:

- Gold permanece 0/3. La medición integrada del 2026-09-07 contiene 97 filas
  distintas, principalmente por método y confianza; no son 97 decisiones de
  clasificación humana. Véase el cierre integrado más abajo.
- Build, smoke, backup cifrado y restore Docker de evaluación están aprobados
  en B2. Faltan actualización, rollback ante fallo real y aceptación supervisada
  de recuperación en el entorno objetivo del cliente.
- Falta elegir el proveedor de identidad, mapear claims y probar roles internos.
- Docker Compose puede negar egress general, pero no implementar por sí solo
  una allow-list FQDN del plano central.
- El cliente debe aprobar custodia de claves, CA, digests de imágenes, retención
  y objetivos RPO/RTO.
- OpenSSL se verificó en el host B2; el smoke comprueba su disponibilidad como
  prerrequisito. Debe comprobarse también en el servidor objetivo del cliente.
- La medición amplia fija de 23 documentos produjo 1 certificado, 5 parciales,
  4 fallidos, 8 no evaluables y 5 timeouts. Es evidencia de cobertura y riesgo,
  no una aprobación de exactitud productiva.
- La auditoría de Neon es parcial: se leyeron 469 validaciones, pero no se
  encontró la vista `promotion_backlog_audit_v1` ni `promotion_outcomes`.
  Esa lectura no acredita el estado de una cola productiva de promociones.

### Formato de control diario

### Trabajo paralelo iniciado el 2026-09-07

Estado actualizado: entregas integradas y verificadas localmente; no constituye cierre de fases ni aprobación de producción.

| Responsable | Alcance | Evidencia de salida requerida |
|---|---|---|
| `gold_pending` | Reproducir Gold y corregir defectos técnicos del certificador sin modificar decisiones humanas ni reducir expectativas | Pruebas y lista precisa de decisiones pendientes en `docs/GOLD_PENDIENTES_20260907.md` |
| `docker_pending` | Verificar paquete y disponibilidad Docker; corregir preflight y scripts; ejecutar smoke aislado si existe daemon | Resultados reales y prerrequisitos pendientes en `docs/DOCKER_PENDIENTES_20260907.md` |
| `promotion_pending` | Revisar fuente real de estados de promociones y preparar contrato/migración revisable | Pruebas y faltantes en `docs/PROMOCIONES_PENDIENTES_20260907.md`; sin mutaciones externas |

La integración revisará los cambios preexistentes y los resultados de cada responsable antes de actualizar fases. Commit, push y despliegue quedan fuera de esta asignación.

### Cierre integrado del 2026-09-07

Cambios locales sobre `c70e60e`, rama `codex/mejoras-pendientes-20260826`.
No se realizó commit, push, despliegue ni escritura en Neon.

| Frente | Avance verificado | Estado restante |
| --- | --- | --- |
| Certificación documental | Certificación final por sección, año y controles de resultados integrada en interfaz; cambios de códigos o revisión invalidan la certificación | Cosemar y Purefruit certificados técnicamente; ABS parcial; Gold exacto 0/3 |
| Política global | Tres decisiones aprobadas aplicadas a balances futuros con pruebas de alcance | Sin sincronización externa; conservar historial y versionar la referencia Gold |
| Paquete on-premise | 45 pruebas de paquete; correcciones de rollback, limpieza y confianza TLS | Smoke real bloqueado por daemon Docker no disponible, salida 69 |
| Promociones | Auditor local SQLite de solo lectura con cinco pruebas; revisión parcial de Neon | Falta fuente productiva con organización y autorización supervisora verificables |

Verificación integrada: 1.290 pruebas recolectadas; **1.273 aprobadas, 17
omitidas y 3 advertencias**, en 59,72 segundos. Las omisiones corresponden a
PDF/SQLite de prueba ausentes y matriz privada sin variable de entorno. La
ejecución fue en Python 3.14 del host, no sustituye la prueba del contenedor
objetivo Python 3.12. `git diff --check` y auditoría estática de módulos aprobaron.

Gold exacto: 97 filas diferentes, con 83 diferencias de método, 37 de confianza
y una de código, superpuestas. El código restante corresponde a la política
global recién aprobada frente a la referencia histórica. No se modificó Gold
para forzar su aprobación. ABS aún requiere trabajo técnico sobre resultado
integral y evidencia de confianza; no es exclusivamente un pendiente humano.

Siguiente orden: ampliar controles de resultado integral y procedencia Gold;
versionar referencias con trazabilidad; ejecutar Docker real; completar controles
de promociones e identidad. La API central, licencias, distribución de maestros
y telemetría requieren su aceptación propia antes del lanzamiento. Las fases
globales permanecen abiertas. Detalle en `AVANCE_PRODUCCION_20260907.md`.

### Campos del cierre diario

### Actualización de cierre 2026-09-07, 21:30 UTC

- Git verificado: HEAD local y rama remota continúan en
  `c70e60eb10fc3cfeebb7ca9c4656ab2ad80824c5`; staging vacío y mejoras locales
  pendientes de publicación. Antigravity trabaja en una copia separada, no integrada.
- B1: entrega recibida y revisada; estado de la entrega pasa de recibida a
  correcciones requeridas. Ninguna fase de producción se cierra.
- Codex ejecutó sobre la copia B1 las suites `tests/antigravity`,
  `tests/persistence/test_block_c_persistence.py` y
  `tests/onprem/test_block_d_backup.py`: 62 aprobadas en 7,07 s, Python 3.14.5.
  Evidencia: `/Users/josealfonsorossel/Desktop/Trabajo Antigravity Homologacion/ronda-b1-20260907/entrega/20260907T212611769407Z-pruebas.log`.
- Bloqueadores revisados: el controlador vuelve a vincular el certificado sin
  preservar el registro documental enriquecido; el formulario de ingreso manual
  sigue certificando directamente sin construir el respaldo estructurado exigido.
  Se entregó al usuario un encargo de corrección para Antigravity. No se acredita
  aún una entrega que cierre estos puntos.
- Gold, Docker real en Python 3.12, recuperación integral, identidad y aislamiento,
  promociones productivas y API central siguen abiertos según el cierre anterior.
  No se reejecutaron esas validaciones en este control; las cifras anteriores no
  constituyen evidencia de B1 integrado ni aceptación de producción.
- Siguiente paso: revisar los recorridos completos de botón e ingreso manual tras
  la corrección, integrar solo los cambios aprobados y repetir regresiones y corpus
  privado. Mantener NO-GO. Sin commit, push, despliegue ni cambios en Neon.

### Actualización documental del 2026-09-08 con auditoría B2

- Trazabilidad: B2 auditó `0e2625df513e63263886e54d7cd4edd90dbedb10`;
  `535ecb1d6410fdfb909dda9228ad2f8a254b4636` incorpora el informe publicado.
- Evidencia B2: gate 1.418; suite 1.401 aprobadas, 17 omitidas, 3 advertencias;
  verificador 49/49 y smoke Docker real de evaluación 8/8, todos con salida 0.
  Suite ejecutada en Python 3.14 host; contenedor de aplicación Python 3.12.
- Fase 4 mantiene `EN_REVISION`; los subcontroles de instalación, persistencia,
  backup cifrado y restore Docker real pasan a aprobados. Las otras fases
  conservan su estado; B2 no acredita cierres adicionales.
- Gold y UAT contable, identidad corporativa y aislamiento dinámico, TLS/red,
  custodia de claves, recuperación humana con RPO/RTO, promociones productivas
  y aceptación de API central siguen pendientes. Las 17 omisiones están
  inventariadas en B2 y requieren resolución antes del acta GO/NO-GO.
- Siguiente paso: ejecutar los controles humanos del entorno objetivo y
  recertificar Gold sobre candidato trazable. Mantener NO-GO para producción.
- Esta actualización sólo reconcilia documentación con evidencia B2; no
  ejecutó nuevamente Docker, suite, Neon ni despliegues.

### Campos de seguimiento diario

1. Cambios realizados, con archivos concretos.
2. Pruebas ejecutadas y resultado exacto.
3. Elementos no verificados.
4. Riesgos o bloqueos nuevos.
5. Estado de cada fase.
6. Cambios propuestos para commit, sin publicarlos hasta aprobación.
7. Trabajo asignado para el siguiente día.
