# Auditoría segura de la cola de promoción

## Resultado actual

Estado al 7 de septiembre de 2026: **verified_partial**.

La consulta de solo lectura de las 17:27:53 UTC verificó 469 validaciones,
dos revisores distintos y cero validaciones sin revisor. No existe la vista
`promotion_backlog_audit_v1` ni la tabla `promotion_outcomes` en la conexión
inspeccionada. No se obtuvo un número de promociones pendientes. Un resultado
ausente no equivale a una cola vacía.

El esquema versionado incorpora metadata de aprobación y outcomes en las
migraciones 003 a 005, pero no modela una cola central completa de candidatos.
La cola usada por la interfaz reside actualmente en
las bases SQLite `gold_records` y `promotion_history`. Contar validaciones de
Neon como pendientes produciría un resultado conceptualmente incorrecto.

## Control reproducible

```bash
python3 scripts/audit_promotion_backlog.py
python3 scripts/audit_promotion_backlog.py --require-verified
```

El segundo comando retorna código 2 mientras la cola no pueda verificarse por
completo. El JSON nunca contiene nombres de cuentas, códigos, montos, RUT,
archivos, revisores ni URL de conexión. Sólo admite:

- conteos por estado;
- cantidad de revisores distintos y de registros sin revisor;
- fechas mínima y máxima;
- actividad agregada de validaciones, marcada explícitamente como distinta de
  una cola de promoción.

La conexión se abre mediante `NeonKnowledgeStore`, solicita una transacción de
solo lectura y ejecuta `rollback` antes de cerrarse. La herramienta no ofrece
operaciones de aprobación, rechazo o promoción.

## Contrato de vista requerido

Para verificar la cola central sin exponer filas individuales debe publicarse
una vista de solo lectura denominada `public.promotion_backlog_audit_v1` con
estas columnas mínimas:

| Columna | Uso permitido |
|---|---|
| `status` | Agrupación por estado de ciclo de vida |
| `created_at` | Antigüedad mínima y máxima |
| `reviewer_id` | Sólo `COUNT(DISTINCT ...)` y conteo de ausentes |

La cuenta técnica usada por el auditor debe tener `SELECT` sobre esa vista y no
debe tener privilegios de escritura sobre tablas operativas. El identificador
del revisor no se devuelve ni se seudonimiza, sólo se cuenta.

## Contraste con la política vigente

La política en `validation/promotion_policy.py` declara el modo
`manual_supervisor`, exige aprobación manual, identidad de supervisor, evidencia
de documento fuente, decisión humana y motivo de clasificación, cero conflictos
y vigencia positiva. La herramienta comprueba ese contrato en memoria.

La presencia de `reviewer_id` en la vista es necesaria para detectar registros
sin responsable, pero no demuestra por sí sola que el actor tenga rol supervisor
ni que exista toda la evidencia mínima. La vista o el servicio que la alimente
debe materializar esos controles antes de una promoción. Esta auditoría no los
reemplaza.

Cuando todos los registros tienen revisor, el contraste devuelve
`not_evaluable` con `approval_evidence_unavailable`, no `compatible`:
identidad presente no demuestra rol, evidencia ni aprobación. La verificación
de conteos (`verification`) y el contraste de política (`policy_contrast`)
son resultados separados.

Si existe `promotion_outcomes`, se informa por separado actividad agregada por
estado y fechas. Sus conteos son eventos históricos, no candidatos actuales.
Un intento fallido seguido de uno aplicado genera dos eventos y no dos asuntos
pendientes. Estos eventos no sustituyen `promotion_backlog_audit_v1`.

## Acción requerida

1. Decidir si la cola central sustituirá o replicará la cola SQLite actual.
2. Crear una migración trazable para los estados y la evidencia de aprobación.
3. Publicar la vista agregada con privilegios estrictamente de lectura.
4. Ejecutar el auditor con `DATABASE_URL` de una cuenta read-only.
5. Investigar estados antiguos y registros sin revisor en la interfaz de
   supervisor. No aprobar ni rechazar en lote desde este auditor.

## Metadata de política implementada

La migración idempotente
`persistence/migrations/003_promotion_policy_metadata.sql` crea un registro
append-only independiente del estado de la cola. Persiste:

- identificador y rol del supervisor autenticado, sin reviewer implícito;
- organización;
- referencias de evidencia, razones y cantidad de conflictos;
- fecha de evaluación y expiración;
- referencia necesaria para una reversión;
- huella SHA-256 canónica para rechazar la reutilización de un
  `evaluation_id` con contenido diferente.

`build_promotion_policy_record` exige rol supervisor o administrador y rechaza
actores genéricos como `analista`, `supervisor` o `system`. La operación de Neon
`save_promotion_policy_metadata` no tiene parámetro `reviewer` ni valor
predeterminado. Un segundo guardado idéntico es idempotente; uno diferente con
el mismo identificador falla.

El camino heredado `save_validation`, que conserva `reviewer="analista"` para
validaciones comunes compatibles, rechaza fuentes identificadas como promoción.
Esas operaciones deben pasar por `save_promotion_policy_metadata`; así el valor
heredado no puede convertirse en aprobación de supervisor.

Esta persistencia todavía no está conectada a la interfaz de aprobación. Debe
integrarse en una única transacción de aplicación antes de considerar que toda
promoción productiva conserva esta evidencia. La tabla por sí sola no modifica
ni autoriza ninguna promoción.

El adaptador on-prem `SqliteOperationalRepository` implementa el mismo contrato
sin depender de Neon. Su tabla local se crea mediante una migración repetible,
incluye huella canónica y bloquea `UPDATE` y `DELETE` mediante triggers. Las
lecturas requieren `organization_id`; una organización distinta recibe ausencia
y no datos de otra organización.

La inicialización local también migra de forma atómica el rol heredado
`administrator` a `admin`. El contrato `UserRole`, el contrato de identidad y el
CHECK de SQLite usan ahora los mismos roles: `analyst`, `supervisor` y `admin`.
Las migraciones aplicadas quedan registradas en `local_schema_migrations`.
