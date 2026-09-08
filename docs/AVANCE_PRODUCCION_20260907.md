# Avance integrado de producción

Fecha: 2026-09-07. Candidato local: rama
`codex/mejoras-pendientes-20260826`, base `c70e60e`.

## Evidencia

- Suite completa: 1.290 recolectadas, 1.273 aprobadas, 17 omitidas y tres
  advertencias en 59,72 s. Registro: `/tmp/onprem-suite-final-20260907.log`.
- Gold privado: certificación técnica 2/3; comparación Gold exacta 0/3.
  Registro: `/tmp/onprem-gold-final-20260907.json`.
- Paquete: 45 pruebas aprobadas. Smoke real: salida 69, daemon no disponible.
- Auditoría estática de módulos y `git diff --check`: salida 0.
- Entorno de suite: Python 3.14. Contenedor objetivo Python 3.12 aún pendiente.

Los registros temporales no son un paquete durable de evidencia de release.
Las 17 omisiones se deben a fixtures PDF/SQLite ausentes y configuración de la
matriz privada; no equivalen a pruebas aprobadas.

## Cambios integrados

1. Certificación final de balances clasificados por período y sección, controles
   de resultados y vínculo con las correcciones efectivas de la interfaz.
2. Políticas globales aprobadas: otros activos financieros a AC.08, otros pasivos
   financieros no corrientes a PNC.05 y costos de distribución a ER.04, con
   restricciones de contexto y códigos existentes conservados.
3. Recuperación local con rollback ante copia fallida o reinicio fallido,
   limpieza acotada y smoke con respaldo cifrado y CA explícita.
4. Auditoría SQLite de promociones sin escritura ni migración, con estado parcial
   cuando no puede acreditarse organización o autorización supervisora.
5. Recolección de pytest con el mismo intérprete que ejecuta el gate.

## Pendientes técnicos antes del control final

- ABS: controles de resultado integral y confianza aún no certificados.
- Gold: revisar procedencia y versionar método/confianza; 97 filas diferentes
  no implican 97 reclasificaciones. Una diferencia de código refleja la nueva
  política global frente al Gold histórico. No se alteró la referencia original.
- Ampliar evidencia de jerarquía: schema 1 no la acredita.
- Promociones: fuente productiva, organización y autorización supervisora.
- Integración y pruebas de identidad; contratos y aceptación de API central,
  licencias, sincronización de maestros y telemetría.
- Sincronización aprobada y verificable de políticas en Neon, aún no ejecutada.
- Entorno Docker real, recuperación, aislamiento y aceptación de usuario.

## Acción humana inmediata

Abrir Docker Desktop y esperar a que el motor esté operativo. Desde el directorio
del candidato, ejecutar:

```sh
docker info
sh deployment/onprem/scripts/verify-package.sh
KEEP_ONPREM_SMOKE_ARTIFACTS=true sh deployment/onprem/scripts/smoke-test.sh
```

El smoke es aislado de evaluación. No es un despliegue productivo ni acredita
identidad corporativa. Compartir el resultado final y la ruta de artefactos,
sin credenciales. Para aceptación productiva faltan CA, digests, custodia de
claves, identidad y objetivos de recuperación del cliente.

No se realizó commit, push, despliegue ni mutación externa en esta integración.
Estado de lanzamiento: pendiente, no aprobado para producción.
