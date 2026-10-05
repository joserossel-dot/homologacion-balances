# Prototipo de despliegue on-premise

Este paquete ejecuta el procesamiento, la base de conocimiento y la interfaz
dentro de la red del cliente. No configura ni requiere Neon.

## Servicios operativos

- `app`: Streamlit, parser, OCR, clasificación y reportes. Se ejecuta con UID
  y GID `10001`, sin privilegios de root.
- `app-volume-init`: prepara con UID/GID `10001` la raíz durable de la
  aplicación y finaliza antes del bootstrap.
- `bootstrap`: crea el bundle local JSON+SQLite y carga de forma no destructiva
  el catálogo y diccionario. Los
  conflictos existentes no se sobrescriben y cada paquete queda versionado por
  checksum.
- `reverse-proxy`: Caddy no-root, HTTPS y única entrada publicada.
- `caddy-volume-init`: tarea efímera que prepara permisos de los volúmenes y
  finaliza antes de iniciar Caddy.
- `db`: PostgreSQL conservado sólo bajo el perfil explícito
  `legacy-postgres`. La aplicación en `PERSISTENCE_MODE=local` no lo consume.

El worker OCR no se incluye todavía. La aplicación actual procesa OCR de forma
síncrona y no produce trabajos para una cola durable. Declarar un worker en
Compose antes de implementar ese contrato daría una falsa capacidad. La
arquitectura objetivo y el criterio para incorporarlo están documentados en
`docs/architecture/on_premise_target.md`.

## Inicio local de evaluación

Este procedimiento activa expresamente el perfil `evaluation`, sin
autenticación. No debe usarse con información productiva.

```bash
cd deployment/onprem
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml ps
```

Abra `https://localhost`. Caddy utiliza una autoridad certificadora interna.
Para evitar la advertencia del navegador, el administrador debe instalar la CA
de Caddy en los equipos autorizados o reemplazar `tls internal` por un
certificado corporativo.

## Verificación reproducible

Sin iniciar contenedores:

```bash
./scripts/verify-package.sh
```

Con Docker activo, el ciclo integral usa un proyecto y volúmenes efímeros y
puertos `18080/18443`. No toca una instalación
existente:

```bash
./scripts/smoke-test.sh
```

Comprueba construcción, bootstrap, salud HTTPS, que el bundle consumido sea
local y operacional, persistencia de auditoría después de reinicio, recuperación
de salud y apagado con eliminación de los volúmenes de prueba. Use
`KEEP_ONPREM_SMOKE_ARTIFACTS=true` sólo para investigar una falla.

## Respaldo y restauración de la persistencia efectiva

`backup-runtime.sh` detiene temporalmente la UI, copia `app_runtime`, genera una
instantánea consistente de SQLite, incorpora un manifiesto con hash y tamaño por
archivo y cifra el artefacto cuando corresponde. Todo respaldo cifrado genera
además `<artefacto>.auth.json`: un sobre HMAC-SHA256 que autentica conjuntamente
los bytes exactos del payload y de sus metadatos. La subclave HMAC se deriva de
la primera línea de `BACKUP_ENCRYPTION_KEY_FILE` con PBKDF2-HMAC-SHA256, salt
aleatorio y separación de dominio; no se reutiliza directamente la clave como
subclave MAC.

`restore-runtime.sh` comprueba primero ese sobre autenticado, antes de interpretar
metadatos, descifrar o detener servicios. Después valida los checksum de
diagnóstico, el manifiesto, JSON y `PRAGMA integrity_check` antes de reemplazar
el volumen. Conserva un respaldo previo y revierte el contenido si la
verificación posterior falla. Los archivos `.sha256` sirven para diagnóstico de
integridad accidental, pero no sustituyen la autenticación criptográfica.

```bash
export BACKUP_ENCRYPTION_KEY_FILE=/ruta/segura/backup.key
export BACKUP_ENCRYPTION_REQUIRED=true
export BACKUP_AUTHENTICATION_REQUIRED=true
ONPREM_DEPLOYMENT_MODE=evaluation \
  ./scripts/backup-runtime.sh
ONPREM_DEPLOYMENT_MODE=evaluation \
  ./scripts/restore-runtime.sh backups/homologacion-app-runtime-FECHA.tar.gz.enc --confirm
```

El nombre real del artefacto cifrado termina en `.tar.gz.enc`; sustituya la
ruta del ejemplo por la devuelta por el comando de respaldo.

En producción, suministre `BACKUP_ENCRYPTION_KEY_FILE` desde una ruta externa y
mantenga `BACKUP_ENCRYPTION_REQUIRED=true`,
`BACKUP_AUTHENTICATION_REQUIRED=true` y
`BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE=false`. `BACKUP_KEY_ID` puede
identificar la versión de clave dentro del sobre, pero no contiene la clave.
Sigue pendiente ejecutar y aceptar el ciclo completo sobre el almacenamiento
objetivo del cliente.

El archivo de clave debe ser un archivo regular, no un enlace simbólico,
pertenecer al mismo usuario efectivo que ejecuta el comando y no conceder
permisos a grupo ni a otros (por ejemplo, modo `0600`). `BACKUP_DIR` debe ser un
directorio real del mismo propietario y no permitir escritura a grupo u otros.
Los scripts crean sus directorios y archivos de trabajo con permisos privados.

La clave se captura una sola vez, antes de cifrar y autenticar el artefacto, y
esa misma captura se usa para ambas operaciones. La copia temporal vive bajo
`TMPDIR`, no dentro de `BACKUP_DIR`. En producción, `TMPDIR` debe apuntar a un
filesystem local, privado, no compartido ni versionado y, cuando corresponda,
cifrado por el cliente. El borrado de la copia temporal no equivale a borrado
forense garantizado por todos los filesystems.

La forma `backup-runtime.sh --source-dir RUTA --confirm-quiesced` es una interfaz
administrativa interna para respaldar una copia que ya está quiescente, como el
rollback creado por `restore-runtime.sh`. No debe usarse sobre una fuente activa.
El uso normal en producción no debe definir `RUNTIME_SOURCE_DIR` ni
`RUNTIME_TARGET_DIR`; ambos overrides están limitados a evaluación.

## Conciliación de artefactos locales

Desde la raíz del repositorio, el comando siguiente es de sólo lectura. Abre una copia estable de la base
operacional y devuelve JSON agregado sin texto OCR, cuentas, montos, nombres de
archivo ni rutas:

```bash
python3 scripts/reconcile_local_runtime.py \
  --root /var/lib/homologacion/runtime scan
```

Para mover exclusivamente los hallazgos reparables de una organización a una
cuarentena recuperable se requiere un administrador autenticado y confirmación
literal:

```bash
python3 scripts/reconcile_local_runtime.py \
  --root /var/lib/homologacion/runtime \
  --temporary-min-age-hours 24 \
  --quarantine-retention-days 90 \
  quarantine \
  --actor-id ID_INMUTABLE --actor-name 'Nombre verificado' \
  --organization-id ID_ORGANIZACION --provider-subject SUBJECT_OIDC \
  --confirm QUARANTINE
```

La restauración valida el manifiesto y no sobrescribe una ruta que reapareció:

```bash
python3 scripts/reconcile_local_runtime.py \
  --root /var/lib/homologacion/runtime \
  restore ID_CASO \
  --actor-id ID_INMUTABLE --actor-name 'Nombre verificado' \
  --organization-id ID_ORGANIZACION --provider-subject SUBJECT_OIDC \
  --confirm RESTORE
```

La retención sólo marca casos vencidos. No existe una orden de purga ni borrado
definitivo; la disposición final requiere una política corporativa aprobada.

## Respaldo PostgreSQL heredado

Los siguientes comandos cubren sólo el PostgreSQL opcional del perfil
`legacy-postgres`; no representan el respaldo de la UI local:

```bash
export BACKUP_ENCRYPTION_KEY_FILE=/ruta/segura/backup.key
export BACKUP_ENCRYPTION_REQUIRED=true
export BACKUP_AUTHENTICATION_REQUIRED=true
ONPREM_DEPLOYMENT_MODE=evaluation \
  ./scripts/backup.sh
ONPREM_DEPLOYMENT_MODE=evaluation \
  ./scripts/restore.sh backups/homologacion-FECHA.dump.enc --confirm
```

El nombre real del artefacto cifrado termina en `.dump.enc`; sustituya la ruta
del ejemplo por la devuelta por el comando de respaldo.

En producción, suministre `BACKUP_ENCRYPTION_KEY_FILE` desde una ruta externa y
mantenga también `BACKUP_AUTHENTICATION_REQUIRED=true` y
`BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE=false`. El artefacto será
`.dump.enc` y tendrá un sidecar `.auth.json` autenticado.

Restore exige el archivo `.sha256`, detiene `app` y `reverse-proxy`, crea un
respaldo previo, restaura en una base de staging y luego intercambia los nombres.
La base anterior se conserva con un nombre fechado para rollback manual. Debe
ensayarse en un ambiente de prueba antes de usarla sobre un cliente.

La migración excepcional de un respaldo antiguo sin `.auth.json` sólo se admite
en evaluación y requiere ambos consentimientos explícitos. No está habilitada en
producción. El mismo contrato de doble consentimiento se aplica a los respaldos
heredados PostgreSQL:

```bash
ONPREM_DEPLOYMENT_MODE=evaluation \
BACKUP_ENCRYPTION_REQUIRED=false \
BACKUP_AUTHENTICATION_REQUIRED=false \
BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE=true \
  ./scripts/restore-runtime.sh RUTA_LEGACY --confirm \
  --allow-legacy-unauthenticated
```

El perfil opcional `legacy-postgres` todavía no valida semánticamente el dump
con `pg_restore --list` antes de publicarlo. Un retorno exitoso y un archivo no
vacío son necesarios, pero no bastan para certificar su restaurabilidad. Esta
limitación no afecta el respaldo primario de `app_runtime`, pero debe cerrarse
antes de certificar ese perfil heredado para producción.

## Límites conocidos del prototipo

1. El contenedor `app` usa filesystem de sólo lectura y declara el fallback JSON
   empaquetado como deshabilitado. El bundle local disponible escribe catálogo, diccionario,
   auditoría, promociones, usuarios, ejecuciones, documentos y reportes bajo
   `/var/lib/homologacion/runtime` en el volumen `app_runtime`. El smoke prueba
   ese bundle y el preflight impide arrancar con Neon, pero la recertificación
   debe confirmar además que todos los caminos de UI consumen el puerto y no una
   ruta heredada directa.
2. El modo local dispone de repositorios durables para documento, ejecución,
   auditoría y reporte, y de conciliación recuperable. La retención de
   cuarentena está acotada y sólo alerta vencimientos; la disposición final no
   se automatiza hasta que el cliente apruebe su política.
3. Producción exige un gateway `forward_auth`, pero el proveedor corporativo,
   claims y separación de roles dentro de la aplicación están pendientes.
4. El worker OCR, la licencia offline y la sincronización firmada de datos
   maestros son diseños pendientes, no funciones incluidas en este Compose.
5. El preflight rechaza tags mutables en producción. Los digests aprobados,
   firma, SBOM y escaneo de vulnerabilidades deben definirse externamente.
6. Backup y restore de `app_runtime` tienen pruebas locales sin daemon y un
   smoke Docker de evaluación que cubre cifrado, autenticación, rechazo de un
   payload alterado con SHA-256 recalculado y restauración válida. Esto no
   certifica producción: el storage definitivo del cliente aún no fue ensayado
   ni aceptado.
7. Antes de producción se deben resolver proveedor de identidad y roles,
   allow-list de egress, custodia de claves, retención, RPO/RTO, distribución de
   CA y digests de imagen aprobados.
8. El sobre HMAC detecta alteraciones del payload y los metadatos, pero no evita
   por sí solo eliminación ni repetición de un respaldo antiguo válido. Un actor
   que comprometa la clave puede crear artefactos autenticados. La protección
   contra esos riesgos depende del almacenamiento inmutable, la custodia y la
   rotación aprobadas por el cliente.
9. Si una restauración y su rollback fallan, el directorio temporal privado se
   conserva como evidencia diagnóstica y puede contener material descifrado y la
   clave capturada. Debe tratarse como evidencia sensible y eliminarse mediante
   el procedimiento aprobado después del análisis.

Los controles y variables de producción están detallados en
`docs/architecture/on_premise_security_controls.md`.
