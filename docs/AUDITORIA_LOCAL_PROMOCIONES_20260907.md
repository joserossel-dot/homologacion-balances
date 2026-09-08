# Auditoría local de promociones

Ejecutar en el nodo que conserva los datos del cliente:

```sh
python3 scripts/audit_local_promotion_backlog.py --source-db /ruta/gold_standard.db --runtime-db /ruta/gold_standard_runtime.db --require-verified
```

Ambas bases deben existir. El auditor abre SQLite mediante `mode=ro` y
`query_only`, sin inicialización ni migración. No comunica datos externamente.
Reutiliza `_classify` de RuntimeManager con conexión de solo lectura para
mantener criterios de candidato. No llama `get_pending_promotions` porque ese
camino abre conexiones ordinarias y transforma algunos errores de esquema en
ausencia de registros; la auditoría debe distinguir ausencia de error de lectura.

El informe contiene únicamente conteos de filas fuente, candidatos, exclusiones,
clasificación, último estado por candidato, eventos históricos y eventos sin
fila fuente. Los últimos estados vacíos o desconocidos son UNKNOWN, sin
convertirse a PENDING. Un candidato sin eventos tiene estado inicial PENDING.
Los candidatos excluidos quedan contados para comprobar la reconciliación con
la fuente completa.

Limitación explícita: las tablas heredadas no ofrecen vínculo verificable de
organización y fuente. Tampoco esta auditoría prueba evidencia del supervisor
ni atomicidad de snapshots entre dos archivos separados. Incluso con conteos
consistentes retorna verified_partial y `--require-verified` sale con código 2.
No debe usarse para certificar aislamiento multiempresa ni aprobar promociones.

Para cerrar esas limitaciones hacen falta identidad persistente de organización,
vínculo estable de cada evento a su base fuente, evidencia de aprobación y un
snapshot coordinado del par de bases. No basta proporcionar una organización
como argumento sin comprobarla contra metadata persistida.
