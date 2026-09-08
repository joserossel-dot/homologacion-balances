# Política global aprobada el 7 de septiembre de 2026

El usuario aprobó estas asignaciones para balances futuros:

| Etiqueta | Código existente |
|---|---|
| Otros activos financieros | AC.08 |
| Otros pasivos financieros no corrientes | PNC.05 |
| Costos de distribución | ER.04 |

Se actualizan las reglas canónicas de `HomologationPipeline` y se agregan las
tres etiquetas al diccionario local con fuente `politica_global_humana_20260907`.
No se redefine ningún código del catálogo. No se modifican referencias Gold
de método ni confianza: las reglas conservan `audited_statement_label`, 0.96.

Las reglas usan coincidencia completa normalizada. Los activos exigen origen
ACTIVO y no se resuelven por esta regla si la sección indica no corriente.
Los otros pasivos financieros no corrientes exigen PASIVO; la variante sin
plazo se resuelve a PNC.05 cuando la sección acredita no corriente. Pasivos
financieros no corrientes sin el término «otros» conservan PNC.01. Los pasivos
financieros corrientes conservan PC.02. Costos de distribución admite etiquetas
de resultado, origen desconocido o ausente; no se aplica como etiqueta canónica
en una fila de pasivo. Subtotales y nombres que agregan otros conceptos no
coinciden con estas reglas completas.

## Alcance de precedencia y sincronización

En `_classify_account` la regla canónica se ejecuta antes del aprendizaje y
del diccionario, por lo que las etiquetas compatibles con el contexto siguen
la política aprobada incluso ante asociaciones históricas distintas.

Neon no se modifica en esta entrega. Los consumidores que solo consultan Neon
o un clasificador distinto deben sincronizar estas tres asignaciones mediante
el proceso de promoción autorizado. La presencia de las reglas en este pipeline
no demuestra sincronización global de todos los consumidores ni del servicio
desplegado.

Las etiquetas ambiguas con una sección incompatible quedan fuera de estas
reglas canónicas. Otros fallbacks heredados del sistema pueden requerir revisión;
esta entrega no convierte una discrepancia de origen en aprobación automática.

## Pruebas

`tests/test_global_human_classification_policy.py` comprueba asignaciones,
normalización, precedencia frente a aprendizaje y contraejemplos de plazo,
origen y subtotales, además de unicidad de entradas exactas en el diccionario.
