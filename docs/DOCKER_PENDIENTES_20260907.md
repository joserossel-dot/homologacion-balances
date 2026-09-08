# Verificación Docker del 7 de septiembre de 2026

Estado: validación estática aprobada; operación real sin verificar.

## Evidencia

- `docker info`: código 1. Cliente 29.5.3 y Compose 5.1.4 disponibles;
  contexto `desktop-linux`, socket del daemon ausente.
- `sh deployment/onprem/scripts/verify-package.sh`: código 0;
  45 pruebas aprobadas en 10,30 segundos, sintaxis y contrato Compose válidos.
  Incluye round-trip local de backup cifrado y restore, y rechazo de modo
  producción sin digests. Dos pruebas de despacho con Docker sustituido validan
  que cleanup y arranque comparten contexto; no son evidencia operacional Docker.
- No se arrancaron servicios, no se construyeron imágenes ni se ejecutó smoke real.

## Cambios realizados

Backup y restore runtime ahora reciben el mismo archivo de variables y override
Compose que utiliza el smoke. Antes sólo resolvían el Compose base, que podía
seleccionar otra imagen o configuración de proxy aunque compartiera el proyecto.
La prueba nueva resuelve Compose real sin daemon y comprueba imagen, build y
nombre aislado del volumen con un archivo de variables cuya ruta contiene espacios.

Restore activa el rollback antes de comenzar el reemplazo, por lo que un fallo
durante la copia ya entra en recuperación. La inyección de fallo mediante stub
comprueba intento de rollback y conservación de código 73; un fallo al reiniciar
servicios produce código 70 y no un mensaje de éxito. Backup tampoco oculta el
fallo de reinicio. El cleanup de un backup fallido antes de asignar archivo destino
no elimina archivos ocultos ajenos del directorio de trabajo. Las llamadas
internas a scripts utilizan `sh` y no dependen del bit ejecutable del checkout.

El smoke selecciona explícitamente el Caddyfile de evaluación. El valor por defecto
del Compose base corresponde a producción y requiere el proveedor de identidad.

## Ejecución pendiente por el operador

En un servidor de pruebas con Docker activo, desde la raíz del repositorio:

```sh
docker info
sh deployment/onprem/scripts/verify-package.sh
KEEP_ONPREM_SMOKE_ARTIFACTS=true sh deployment/onprem/scripts/smoke-test.sh
```

Sólo ejecutar la tercera instrucción si las dos primeras terminan correctamente.
El smoke utiliza un proyecto `homologacion-smoke-<PID>` y puertos 18080/18443.
El procedimiento elimina sus propios contenedores y volúmenes al finalizar;
con la variable indicada conserva archivos de evidencia y respaldo temporales.
Conservar la salida completa y registrar el commit candidato utilizado.

## Alcance pendiente de certificación

El smoke de evaluación valida construcción, arranque, salud, persistencia,
backup cifrado y restore runtime. Curl utiliza `--cacert` con la CA extraída
del contenedor Caddy del proyecto aislado. La clave temporal del backup se
genera con OpenSSL; con artefactos conservados también se conserva esa clave
en el directorio privado del ensayo. No es la custodia definitiva de claves.
No certifica CA corporativa, identidad ni rollback después de un fallo real.
Tampoco prueba PostgreSQL, que sólo figura
en el perfil legacy y no es la persistencia local operacional activa.
Esos controles requieren la ejecución adicional de aceptación de producción.

El daemon inactivo impide confirmar que las correcciones de contexto resuelvan
todo el recorrido operativo. No debe presentarse el resultado estático como
aprobación del paquete para producción.

## Ensayo con configuración de producción

Después de publicar y aprobar imágenes por digest, exportar
`APP_IMAGE_REFERENCE`, `POSTGRES_IMAGE`, `CADDY_IMAGE` y `CADDY_INIT_IMAGE`
con referencias `repositorio@sha256:...` reales. Ejecutar:

```sh
ONPREM_SMOKE_MODE=production KEEP_ONPREM_SMOKE_ARTIFACTS=true sh deployment/onprem/scripts/smoke-test.sh
```

Este modo valida primero los requisitos de imágenes inmutables, no construye
imágenes y utiliza el Caddyfile de producción con autenticación cerrada por
defecto. El healthcheck está permitido sin identidad. No debe interpretarse
su éxito como prueba de acceso autenticado ni aislamiento de usuarios.
El ensayo usa únicamente sus volúmenes nuevos, tanto para escribir el marcador
como para alterarlo y restaurarlo. No reutiliza datos del cliente.
