# Inventario de migraciones

Revisión de código: 2026-09-10. No acredita aplicación en una base remota.

| Ruta | Destino | Ejecución |
| --- | --- | --- |
| `migrations/001_neon_knowledge.sql` | PostgreSQL | `NeonKnowledgeStore.initialize` |
| `migrations/002_unify_accumulated_results.sql` | PostgreSQL | Migración histórica manual, no ejecutada automáticamente por el inicializador |
| `persistence/migrations/` | PostgreSQL | Extensiones de persistencia; consultar los inicializadores explícitos de `neon_store.py` y herramientas de administración |
| `persistence/local/migrations/` | SQLite | `sqlite_operational.py` aplica las migraciones locales durante la inicialización |

Los números se interpretan dentro de cada ruta, no como una secuencia global.
No concatenar los tres directorios ni ejecutar SQL PostgreSQL sobre SQLite.

## Restricciones de la unificación histórica

`002_unify_accumulated_results.sql` modifica tanto el diccionario como registros
de validación e historial. No incorporarla al arranque automático: reescribir
esas columnas altera la evidencia histórica de decisiones. Antes de aplicarla
se debe comprobar el estado real, obtener respaldo y definir una migración que
preserve los códigos originales de auditoría y registre la equivalencia canónica.
Este inventario no autoriza su ejecución ni confirma que haya sido aplicada.

## Verificación pendiente

Protección PostgreSQL añadida en `006_policy_append_only.sql` y
`007_outcomes_append_only.sql`: rechaza UPDATE, DELETE y TRUNCATE del historial.
Los inicializadores explícitos las incorporan; 007 se aplica después de 005.
Aplicadas con autorización en Neon PostgreSQL 18.6 el 2026-09-10.
También probadas sobre PostgreSQL 16;
verificar compatibilidad antes de usar otra versión. Un administrador con permisos para
deshabilitar o eliminar triggers puede sortear esta protección; no sustituye
la separación del rol de aplicación respecto del propietario del esquema.

### Aplicación autorizada en Neon, 2026-09-10

Las tablas estaban ausentes. Se aplicaron 003, 004, 005, 006 y 007 en una
transacción. Antes del commit se verificaron seis rechazos con SQLSTATE 23514:
UPDATE, DELETE y TRUNCATE en ambas tablas. Las filas sintéticas se revirtieron
mediante savepoint. Después del commit, una conexión nueva confirmó cuatro
triggers habilitados y cero registros en ambas tablas.

Respaldo previo privado fuera del repositorio: archivo custom de pg_dump 18,
72.519 bytes, SHA256
`f42b0a07775b80aef35561d8fb4b561bf93a540dbf0017fc1af3d6f3677383e0`.
pg_restore pudo listar el archivo. No se ejecutó una restauración completa;
la lectura del índice no certifica recuperación integral.

Verificación ejecutada el 2026-09-10: `tests/persistence/test_migration_dialects.py`
aplica dos veces las migraciones 003 y 004 en SQLite en memoria y PostgreSQL 16
temporal en Docker. Comprueba inserción válida, rechazo de rol inválido y clave
primaria duplicada. Activación: `RUN_POSTGRES_MIGRATIONS=1 pytest
tests/persistence/test_migration_dialects.py`. Sin esa variable, el caso
PostgreSQL queda omitido explícitamente. No publica puertos ni monta volúmenes;
el contenedor se detiene y elimina al finalizar.

Resultado conjunto de persistencia, arquitectura y calidad operativa:
112 pruebas aprobadas. Esto no cubre equivalencia completa de restricciones,
ni las transacciones de los repositorios contra PostgreSQL.

Las pruebas de cada backend no equivalen a una prueba de paridad contra un
PostgreSQL real. Antes de declarar paridad, ejecutar el mismo contrato de
persistencia en SQLite y PostgreSQL aislados, incluyendo restricciones,
idempotencia, transacciones y resultados de promoción. No usar Neon productivo
para esta prueba. La separación de dialectos no justifica fusionar directorios.
