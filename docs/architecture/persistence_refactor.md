# Inicio de refactorización de persistencia

## Estado

Contratos y adaptadores iniciales implementados. La carga y escritura de
catálogo, diccionario y validaciones del flujo Streamlit ya se resuelven mediante
la factoría. No se realizaron migraciones de datos Neon.

## Diagnóstico del estado heredado

Existían dos rutas de persistencia con modelos diferentes. La ruta
`src/db_repository.py` y la API que la consumía fueron retiradas el 2026-08-30:
no eran entrypoints, el orquestador no implementaba el método invocado y esa
ruta desactivaba la verificación TLS. Permanece la ruta operativa:

1. `persistence/neon_store.py` implementa catálogo, diccionario, validaciones,
   historial, estadísticas, conflictos y rollback mediante PostgreSQL síncrono.

La aplicación Streamlit y el pipeline usan `NeonKnowledgeStore`. No permanece
ningún consumidor del repositorio retirado.

Problemas concretos:

- el esquema retirado era incompatible con el esquema operativo;
- conexión, migración, lectura, aprendizaje y auditoría están mezclados;
- la aplicación mantiene fallback de escritura JSON fuera del repositorio;
- documentos, ejecuciones, usuarios y reportes tienen adaptadores locales
  transitorios, aún no integrados al flujo Streamlit;
- `DATABASE_URL` decide simultáneamente almacenamiento y comportamiento;
- el nombre Neon describe un proveedor, no la responsabilidad del componente.

La revisión estática del flujo actual no encontró consumidores productivos de
`LocalDocumentRepository`, `LocalExecutionRepository`, `LocalAuditRepository`
ni `LocalReportRepository`: hasta este cambio sólo la factoría y las pruebas los
construían. Los registros documentales y de ejecución permiten metadatos, pero
no tienen una columna tipada de organización; `AuditEvent.actor_id` admite
ausencia y `ReportRecord` sólo se vincula por ejecución. La nueva unidad de
proceso cierra esos huecos en su frontera al exigir `AuthenticatedActor`, copiar
organización y actor a documento/ejecución, y autorizar reportes y auditoría a
través de la ejecución. Los repositorios crudos conservan compatibilidad y no
deben exponerse directamente a la interfaz multi-organización.

## Contratos incorporados

| Contrato | Responsabilidad |
|---|---|
| `LocalKnowledgeRepository` | catálogo, diccionario y decisiones humanas |
| `LocalDocumentRepository` | contenido original, hash y metadatos mínimos |
| `LocalExecutionRepository` | ciclo de vida de un procesamiento |
| `LocalAuditRepository` | eventos append-only por sujeto |
| `LocalUserRepository` | registro local de usuario durante la transición |
| `PromotionPolicyRepository` | evaluación y outcome batch append-only de promoción |
| `IdentityProvider` | autenticación corporativa provider-neutral |
| `AuthenticatedActor` | actor, organización y roles verificados |
| `LocalReportRepository` | reportes vinculados a una ejecución |
| `LocalProcessPersistence` | saga local documento, ejecución, auditoría y reporte |
| `LicenseClient` | activación y renovación de licencia |
| `MasterDataClient` | manifiesto y descarga de paquetes maestros |
| `TelemetryClient` | eventos técnicos de esquema cerrado |

Los contratos viven en `persistence/contracts`. No dependen de Streamlit,
PostgreSQL, Neon, FastAPI ni HTTP.

## Identidad, roles y auditoría

El contrato canónico define `analyst`, `supervisor` y `admin`. No selecciona
OIDC, Active Directory ni otro proveedor. `DenyAllIdentityProvider` es el valor
seguro inicial: sin un adaptador autenticador explícito, no entrega identidad.

`audit_event_for_actor()` exige un `AuthenticatedActor` y propaga `actor_id`,
`organization_id` y roles al evento. No acepta acciones auditables anónimas ni
copia credenciales. Esta interfaz aún no reemplaza el usuario literal usado por
Streamlit; esa integración requiere modificar el consumidor y una decisión
sobre proveedor.

El almacenamiento local usa el rol canónico `admin`. Al abrir una base creada
por una versión anterior, una migración transaccional reconstruye el CHECK y
traduce `administrator` a `admin`, preservando los demás campos. La aplicación
de la migración se registra en `local_schema_migrations`. Esto normaliza el rol
almacenado, pero no sustituye la futura fuente de identidad corporativa.

## Adaptadores iniciales

### `LegacyNeonKnowledgeAdapter`

Conserva el comportamiento actual. Traduce `ValidationDecision` al diccionario
de argumentos aceptado por `NeonKnowledgeStore` y delega nuevas categorías con
`save_catalog_entry`. Permite migrar consumidores al contrato antes de
reemplazar la implementación.

### `JsonKnowledgeRepository`

Adaptador transicional para catálogo y diccionario locales. Actualiza ambos JSON
mediante sustitución atómica, serializa escritores con locks de archivo y
conserva historiales JSONL. Toda validación queda auditada, incluso cuando
`add_to_dictionary=False`; sólo las decisiones con ese indicador activo mutan
el diccionario. Una categoría nueva se inserta de forma idempotente, pero una
redefinición conflictiva del mismo código se rechaza. No debe ser la fuente
productiva de una instalación multiusuario.

### `FileDocumentRepository`

Guarda cada documento bajo un identificador generado, elimina rutas del nombre
original y verifica SHA-256 en cada lectura. No implementa eliminación ni
retención todavía.

### `FileReportRepository`

Guarda reportes por ejecución, identifica borrador o definitivo y verifica
SHA-256 en lectura.

### `SqliteOperationalRepository`

Implementa ejecuciones, auditoría, usuarios y metadata append-only de políticas
de promoción en SQLite con WAL, sincronización FULL, transiciones de estado
cerradas y actualización optimista. Cada evaluación permitida se vincula a un
único outcome lógico de batch que conserva todos los `promotion_ids` generados.
`APPLIED` y `FAILED` cierran la evaluación; la ausencia de outcome y
`INCONSISTENT` permanecen bloqueantes y son consultables por sujeto y
organización después de reiniciar. Los registros son append-only y una
repetición exacta es idempotente. Es durable para pruebas o una instalación
individual. El despliegue corporativo multiusuario requiere un adaptador
PostgreSQL con los mismos contratos.

### `LocalProcessPersistenceService`

Compone los repositorios de documentos, ejecuciones, auditoría y reportes sin
crear una segunda base de datos. `PersistenceBundle.processes` lo expone cuando
la persistencia operacional está habilitada. Su interfaz es:

- `start(content, original_name, media_type, scope, actor, application_version)`;
- `get(execution_id, actor)`;
- `mark_review(execution_id, actor)`;
- `record_correction(execution_id, actor, correction_id, classification_code)`;
- `complete_with_report(execution_id, content, actor, file_name, media_type)`;
- `fail(execution_id, actor, error_code)`;
- `list_audit(execution_id, actor, limit)`;
- `read_definitive_report(execution_id, report_id, actor)`.

`ProcessScope` conserva explícitamente si se analizaron todas las páginas o una
selección ordenada, además de uno o dos períodos. La organización y el actor se
copian tanto al documento como a la ejecución; todos los accesos del servicio
validan la organización antes de leer auditoría o reportes. Las correcciones
registran identificador y código de clasificación, sin copiar texto OCR ni
montos al evento.

Los archivos y SQLite no comparten una transacción distribuida. Por eso el
servicio implementa una saga compensable y no declara atomicidad: ante un fallo
posterior intenta dejar la ejecución en `failed`, devuelve en
`ProcessPersistenceError` los IDs de artefactos que requieren conciliación y
no permite descargar un reporte definitivo si la ejecución no terminó en
`completed`. Si falla la creación de la ejecución después de guardar el
documento, intenta registrar un evento de documento huérfano.

### `LocalRuntimeReconciler`

Inspecciona la raíz durable y detecta documentos sin ejecución, ejecuciones sin
documento, reportes sin ejecución, hashes inválidos y archivos `.tmp` que
superan la antigüedad configurada. `scan()` no modifica artefactos y su salida
agregada contiene sólo conteos, fecha y vencimientos de retención: no incluye
rutas, nombres de cuentas, texto OCR, importes ni contenido documental.

La reparación no se activa por el escaneo. `quarantine()` exige un
`AuthenticatedActor` con rol `admin`, limita los movimientos a la organización
del actor, registra eventos append-only y mueve cada candidato a un caso con
manifiesto, checksum y plazo de conservación. Si una etapa falla, intenta
revertir todos los movimientos del caso. `restore()` valida organización,
estado, rutas y hashes antes de devolver los artefactos, y se detiene si la ruta
original ya existe. No existe una operación de borrado definitivo: un caso cuyo
plazo venció se cuenta como pendiente de decisión humana y sigue siendo
restaurable.

El operador usa `scripts/reconcile_local_runtime.py`. El modo predeterminado
abre una copia estable de SQLite para impedir que una consolidación interna del
WAL modifique la base inspeccionada. Las operaciones de cuarentena y
restauración requieren subcomando, identidad completa y confirmación literal.
La antigüedad de temporales se restringe a 1..8760 horas y la retención de
cuarentena a 1..3650 días.

## Flujo objetivo

```text
Interfaz y pipeline
      |
      +--> LocalProcessPersistence
      +--> LocalKnowledgeRepository
      +--> LocalDocumentRepository
      +--> LocalExecutionRepository
      +--> LocalAuditRepository
      +--> LocalUserRepository
      `--> LocalReportRepository

Agente del plano de control
      |
      +--> LicenseClient
      +--> MasterDataClient
      `--> TelemetryClient
```

Los clientes remotos no reciben referencias a repositorios locales ni cadenas
de conexión. La serialización inicial de telemetría expone una lista cerrada de
campos técnicos.

## Compatibilidad

La migración no modifica:

- parsers o pipeline;
- `NeonKnowledgeStore`;
- esquema o datos Neon;
- Docker, Render o workflows.

La aplicación selecciona explícitamente el repositorio de conocimiento mediante
`build_persistence()`. En modo local, un error durable bloquea el fallback hacia
los JSON empaquetados; en modo heredado se conserva Neon y su fallback anterior.
Los tabs administrativos Neon permanecen fuera del puerto y sólo se habilitan
cuando Neon está disponible.

## Factoría y selección explícita

`persistence.factory.build_persistence()` constituye el primer seam de
integración. No abre conexiones al importarse y utiliza `legacy_neon` por
defecto.

| Variable | Uso | Predeterminado |
|---|---|---|
| `PERSISTENCE_MODE` | `legacy_neon` o `local` | `legacy_neon` |
| `LOCAL_PERSISTENCE_ROOT` | raíz durable local | sin valor |
| `LOCAL_CATALOG_SEED` | semilla inicial del catálogo | JSON del proyecto |
| `LOCAL_DICTIONARY_SEED` | semilla inicial del diccionario | JSON del proyecto |
| `ENABLE_OPERATIONAL_PERSISTENCE` | activa documentos, ejecución, auditoría, usuarios y reportes junto a Neon | `false` |
| `LOCAL_MASTER_BUNDLE_VERSION` | versión declarada de la semilla local | `embedded` |

Ejemplos:

```text
# Comportamiento heredado, sin crear archivos operativos
PERSISTENCE_MODE=legacy_neon

# Neon para conocimiento y almacenamiento operativo local nuevo
PERSISTENCE_MODE=legacy_neon
ENABLE_OPERATIONAL_PERSISTENCE=true
LOCAL_PERSISTENCE_ROOT=/ruta/durable/homologacion

# Operación completamente local, sin instanciar Neon
PERSISTENCE_MODE=local
LOCAL_PERSISTENCE_ROOT=/ruta/durable/homologacion
```

En modo local las semillas sólo se copian cuando el destino no existe. Un
reinicio nunca reemplaza el conocimiento local ya actualizado. El primer
paquete queda `activated` en `knowledge/seed-state.json`; un checksum nuevo se
registra como `update_pending` en el historial y requiere una migración explícita.

## Secuencia de migración recomendada

### Paso 1. Conocimiento

1. Crear una fábrica que entregue `LocalKnowledgeRepository`.
2. En ambiente actual, usar `LegacyNeonKnowledgeAdapter`.
3. Reemplazar instancias directas de `NeonKnowledgeStore` en Streamlit y
   pipeline por inyección del contrato.
4. Mantener pruebas de equivalencia para carga, validación, lote y rollback.
5. Trasladar estadísticas, conflictos e historial a contratos administrativos
   separados, evitando ampliar indefinidamente `LocalKnowledgeRepository`.

Estado: factoría, configuración, compatibilidad Neon, modo local sin red y
consumo Streamlit para catálogo, diccionario y validaciones ya están
implementados. El pipeline y las funciones administrativas Neon todavía no se
han migrado completamente a contratos separados.

### Paso 2. Documento y ejecución

1. Guardar el documento antes de extraerlo.
2. Crear una ejecución vinculada al hash documental y versión del software.
3. Registrar selección de páginas y período en metadatos estructurados.
4. Actualizar estado en cada frontera del pipeline.
5. Agregar eventos auditables sin texto OCR ni contenido sensible en logs.

### Paso 3. Usuarios y reportes

1. Resolver la identidad desde el proveedor corporativo.
2. Mapear los grupos corporativos exclusivamente a `analyst`, `supervisor` y
   `admin`; todo grupo sin mapeo se deniega.
3. Los registros locales `administrator` se migran atómicamente a `admin` al
   abrir el repositorio; el contrato y el CHECK ya usan el rol canónico.
4. Sustituir el usuario literal `analista` por `actor_id` autenticado.
5. Vincular cada decisión y reporte con actor y ejecución.
6. Guardar el reporte antes de ofrecer descarga.
7. Aprobar la disposición final de cuarentenas vencidas; el sistema sólo las
   informa y no las elimina automáticamente.

### Paso 4. PostgreSQL local

1. Implementar los seis contratos locales sobre PostgreSQL.
2. Incorporar migraciones versionadas, sin crear esquema al importar.
3. Ejecutar pruebas de concurrencia y transacciones.
4. Migrar JSON, SQLite y conocimiento Neon mediante una herramienta explícita.
5. Comparar conteos, hashes y decisiones antes de retirar fallbacks.

### Paso 5. Plano central

1. Implementar clientes HTTP fuera de repositorios locales.
2. Validar licencia firmada localmente.
3. Validar firma y hash del paquete maestro antes de activarlo.
4. Rechazar telemetría con campos no permitidos.
5. Probar operación durante indisponibilidad de la API.

## Reglas de implementación

- ninguna capa de dominio lee directamente `DATABASE_URL`;
- ningún repositorio abre conexiones al importarse;
- las migraciones se ejecutan mediante una operación explícita;
- documentos y reportes se identifican por ID, no por rutas suministradas;
- toda lectura binaria valida integridad;
- auditoría es append-only;
- errores remotos no alteran transacciones locales confirmadas;
- las pruebas de adaptadores no usan servicios externos;
- una migración no elimina el respaldo de origen hasta completar conciliación.

## Riesgos y pendientes

1. Los adaptadores de archivos no cifran contenido en reposo.
2. Existe retención configurable para cuarentena, sin borrado definitivo. La
   política corporativa de disposición final todavía requiere aprobación.
3. SQLite no sustituye PostgreSQL para concurrencia corporativa.
4. El historial JSONL no sustituye una auditoría transaccional multiusuario.
5. Los contratos remotos aún no implementan firma, autenticación ni transporte.
6. Falta seleccionar y configurar el proveedor corporativo de identidad.
7. Falta definir el mapeo aprobado de grupos, caducidad de sesión, MFA y cuenta
   de emergencia.
8. La CA, rotación de certificados y política exacta de TLS de PostgreSQL son
   decisiones de infraestructura; no se permite reintroducir `CERT_NONE`.
9. La unidad compensable existe, pero la interfaz Streamlit todavía debe
   cablearse exclusivamente a `PersistenceBundle.processes`; acceder a los
   repositorios crudos elude el aislamiento organizacional del servicio.
10. Una escritura binaria huérfana queda identificada y auditable, pero falta
   definir retención, conciliación y eliminación supervisada del artefacto.

## Evidencia automatizada

`tests/persistence/test_persistence_contracts.py` verifica:

- cumplimiento estructural de contratos;
- compatibilidad con la forma actual de Neon;
- actualización JSON atómica;
- inserción de categorías durable, idempotente y sin redefinición silenciosa;
- auditoría de decisiones de caso único sin contaminación del diccionario;
- saneamiento de nombres y bloqueo de traversal;
- integridad SHA-256 de documentos y reportes;
- durabilidad SQLite de ejecuciones, usuarios y auditoría;
- roles cerrados y fallas explícitas;
- forma cerrada de telemetría.

`tests/persistence/test_process_service.py` verifica reinicio, alcance de
páginas y períodos, auditoría de correcciones, reporte final, aislamiento por
organización y compensación ante un fallo parcial después de escribir el
reporte.

Este conjunto no certifica todavía el adaptador PostgreSQL productivo ni una
migración de datos real.
