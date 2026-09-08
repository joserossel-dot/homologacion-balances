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
archivo y cifra el artefacto cuando corresponde. `restore-runtime.sh` verifica
checksum, metadatos, manifiesto, JSON y `PRAGMA integrity_check` antes de
reemplazar el volumen. Conserva un respaldo previo y revierte el contenido si la
verificación posterior falla.

```bash
ONPREM_DEPLOYMENT_MODE=evaluation BACKUP_ENCRYPTION_REQUIRED=false \
  ./scripts/backup-runtime.sh
ONPREM_DEPLOYMENT_MODE=evaluation BACKUP_ENCRYPTION_REQUIRED=false \
  ./scripts/restore-runtime.sh backups/homologacion-app-runtime-FECHA.tar.gz --confirm
```

En producción, suministre `BACKUP_ENCRYPTION_KEY_FILE` desde una ruta externa y
mantenga `BACKUP_ENCRYPTION_REQUIRED=true`. Sigue pendiente ejecutar y aceptar
el ciclo completo con un daemon Docker y el almacenamiento objetivo del cliente.

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
ONPREM_DEPLOYMENT_MODE=evaluation BACKUP_ENCRYPTION_REQUIRED=false \
  ./scripts/backup.sh
ONPREM_DEPLOYMENT_MODE=evaluation BACKUP_ENCRYPTION_REQUIRED=false \
  ./scripts/restore.sh backups/homologacion-FECHA.dump --confirm
```

En producción, suministre `BACKUP_ENCRYPTION_KEY_FILE` desde una ruta externa y
mantenga `BACKUP_ENCRYPTION_REQUIRED=true`. El artefacto será `.dump.enc`.

Restore exige el archivo `.sha256`, detiene `app` y `reverse-proxy`, crea un
respaldo previo, restaura en una base de staging y luego intercambia los nombres.
La base anterior se conserva con un nombre fechado para rollback manual. Debe
ensayarse en un ambiente de prueba antes de usarla sobre un cliente.

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
6. Backup y restore de `app_runtime` tienen pruebas locales sin daemon, pero el
   recorrido sobre un volumen Docker real y el storage definitivo del cliente
   aún no fue ejecutado ni aceptado.
7. Antes de producción se deben resolver proveedor de identidad y roles,
   allow-list de egress, custodia de claves, retención, RPO/RTO, distribución de
   CA y digests de imagen aprobados.

Los controles y variables de producción están detallados en
`docs/architecture/on_premise_security_controls.md`.
