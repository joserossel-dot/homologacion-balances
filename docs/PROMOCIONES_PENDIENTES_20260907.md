# Cierre técnico de auditoría de promociones

## Evidencia verificada

- 2026-09-07 17:27:53 UTC: auditoría real en transacción de solo lectura,
  seguida de rollback y cierre de conexión.
- Neon: 469 validaciones; dos revisores distintos; cero revisores ausentes.
- `promotion_backlog_audit_v1` y `promotion_outcomes` no existen en esa conexión.
- Resultado `verified_partial`; tamaño y antigüedad de la cola desconocidos.
- `python3 -m pytest tests/architecture/test_audit_promotion_backlog.py tests/persistence/test_promotion_audit_scope.py -q`:
  nueve pruebas aprobadas.
- No se aplicaron migraciones ni otras escrituras en Neon.

## Mejora entregada

El auditor distingue tres fuentes: validaciones, cola de candidatos y eventos
de resultado de promociones. Solo la segunda puede certificar conteos de cola.
Los eventos de resultado, si existen, se agregan sin exponer actores, asuntos,
errores ni información contable. Tener revisor en todas las filas dejó de
producir una evaluación `compatible`; sigue faltando comprobar rol, aprobación,
evidencia y conflictos.

## Por qué no se creó una vista artificial

`promotion_policy_metadata` contiene evaluaciones, no el universo de candidatos.
`promotion_outcomes` contiene APPLIED, FAILED e INCONSISTENT, no el ciclo completo
de pendientes, rechazos y reversiones. `log_validaciones` tampoco representa
ese ciclo. Una vista sobre esas fuentes omitiría candidatos sin evaluación y
podría contar varios intentos como varias cuentas pendientes.

La fuente local utiliza `gold_records`, `promotion_history` y
`RuntimeManager.get_pending_promotions`. No existe en el código inspeccionado
una réplica central completa de esa fuente. Por ello no se entrega una
migración que afirme exponer una cola central completa.

## Trabajo técnico pendiente y decisión de producto

Para el despliegue on-premise, la ruta propuesta es certificar la cola en el
nodo del cliente y enviar únicamente métricas autorizadas al plano central.
Antes de implementar la alternativa central debe quedar decidido si Neon
será una cola operativa o recibirá solo métricas. Esa decisión afecta el
contrato de privacidad ya planteado y la ubicación de la autoridad de aprobación.

Una cola central requeriría identificador estable por organización/nodo/candidato,
estados persistentes con historial, aprobación y reversión, deduplicación,
transiciones atómicas y evidencia de completitud de sincronización. Los datos
históricos no deben convertirse en aprobaciones mediante valores por defecto.

Una vez implementada la fuente autorizada: preparar migración revisable,
privilegios SELECT del auditor, pruebas de separación por organización y
auditoría real. Aplicar únicamente las migraciones 003 a 005 no cierra la cola.

## Instrucción humana mínima

El responsable de arquitectura debe registrar cuál de estas dos ubicaciones
será la autoridad de la cola: nodo local del cliente o servicio central. Para
el modelo on-premise con datos contables locales, se propone nodo local.
Después el administrador habilitará una cuenta de auditoría de solo lectura
en esa fuente. No es necesario reclasificar las 469 validaciones ni aprobarlas
en lote para resolver este bloqueo.
