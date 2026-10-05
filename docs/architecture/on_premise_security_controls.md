# Controles de seguridad del paquete on-premise

## Alcance

Este documento describe controles implementados y límites verificables del
prototipo. No constituye una aprobación de producción.

## Autenticación provider-neutral

El perfil de producción monta `Caddyfile.production`. Toda ruta, salvo el
healthcheck, pasa por `forward_auth`. La variable `AUTH_GATEWAY_URL` identifica
un gateway corporativo compatible con este contrato:

- Caddy envía la solicitud de verificación al path configurado;
- una respuesta 2xx autoriza el acceso;
- cualquier rechazo o indisponibilidad impide llegar a Streamlit;
- el gateway puede devolver `X-Authenticated-User` y
  `X-Authenticated-Roles`;
- la aplicación todavía no consume esos encabezados para autorización interna.

Sin gateway configurado, la URL predeterminada apunta a un puerto local cerrado.
El resultado es denegación por defecto, no acceso anónimo. Para evaluación se
debe declarar explícitamente `ONPREM_DEPLOYMENT_MODE=evaluation` y montar el
`Caddyfile` sin autenticación. Ese perfil no es apto para datos productivos.

El proveedor, los claims, grupos, expiración de sesión, MFA y cierre de sesión
son decisiones del cliente. OIDC, Active Directory u otro proveedor pueden
ubicarse detrás del mismo hook, pero no están implementados.

## Egress

Las redes `data` y `frontend` están marcadas como internas. La aplicación,
PostgreSQL y Caddy no reciben una red Docker con salida general a internet. Un
gateway de autenticación usado por este Compose debe ser local y compartir una
red interna controlada.

Docker Compose puede negar salida mediante redes internas, pero no expresa una
allow-list fiable por FQDN, certificado o endpoint. La futura conexión al plano
central requiere un sidecar o proxy de egress separado, unido a una red externa,
más reglas del firewall del cliente. No se debe conectar `app` directamente a
esa red.

## Imágenes inmutables

`preflight.py` rechaza el modo `production` si cualquiera de estas referencias
no usa `@sha256:<digest>`:

- aplicación;
- PostgreSQL;
- Caddy;
- inicializador Caddy.

El Compose de producción sólo consume `APP_IMAGE_REFERENCE`; no contiene
`build`. El build local y su imagen base parametrizada existen únicamente en
`docker-compose.evaluation.yml`.

La evaluación admite tags mutables sólo cuando se declara expresamente. La
selección de registry, digest aprobado, SBOM, firma y escáner permanece pendiente.

## Backup y restore

En producción, `backup-runtime.sh` exige una clave externa no vacía y cifra el
snapshot de `app_runtime`
con AES-256-CBC, PBKDF2 y salt. La clave no entra a la imagen ni al repositorio.
Además genera un sobre HMAC-SHA256 que cubre los bytes exactos del artefacto y
de sus metadatos de RPO, RTO, retención, formato y fecha. La subclave HMAC se
deriva mediante PBKDF2-HMAC-SHA256 con salt aleatorio y separación de dominio.
Los checksum SHA-256 sin clave se conservan como diagnóstico, no como prueba de
autenticidad. La retención elimina artefactos más antiguos dentro del directorio
de backup explícito.

La clave se valida como archivo regular, no simbólico, perteneciente al usuario
efectivo y sin permisos para grupo u otros. Se captura una sola vez antes del
cifrado y la firma para impedir que una rotación concurrente produzca un bundle
autenticado con una clave distinta de la usada para cifrar. `BACKUP_DIR` también
debe ser un directorio real, del operador y sin escritura de grupo u otros. La
publicación usa staging privado, no sobrescribe nombres existentes y hace visible
el payload principal al final, después de sus sidecars.

`restore-runtime.sh` verifica el HMAC antes de leer metadatos, descifrar o detener
servicios. Sólo después comprueba checksum, manifiesto cerrado, hashes por
archivo, JSON e integridad SQLite. Extrae en staging, crea un respaldo previo
cifrado y autenticado y, si falla la sonda posterior al reemplazo, recupera el
snapshot anterior. Las pruebas sin daemon cubren round-trip, traversal,
alteración de manifiesto, payload o metadatos, clave incorrecta y conservación
del destino ante un archivo inválido. Un smoke Docker de evaluación verificó el
rechazo de un payload alterado aun después de recalcular su SHA-256, seguido por
la restauración válida y la recuperación de salud. Esta prueba no acredita el
storage real del cliente, que sigue pendiente.

Para reducir cambios entre verificación y uso, restore trabaja sobre copias
privadas y estables del payload, metadatos y sidecars, y conserva una captura
estable de la clave. Estas copias viven bajo `TMPDIR`; el cliente debe configurar
un filesystem local, privado, no compartido ni versionado y, si su política lo
exige, cifrado. El borrado lógico de la captura de clave no garantiza borrado
forense en todos los filesystems.

La opción administrativa `backup-runtime.sh --source-dir RUTA
--confirm-quiesced` sólo respalda una fuente cuya quiescencia ya fue confirmada.
Se usa internamente para el snapshot previo de restore; no sustituye la detención
de una fuente activa. Los overrides `RUNTIME_SOURCE_DIR` y `RUNTIME_TARGET_DIR`
no están permitidos en producción.

`backup.sh` y `restore.sh` permanecen únicamente para el perfil explícito
`legacy-postgres`; no protegen la persistencia operativa de la UI local. Ese
backup heredado aún no ejecuta `pg_restore --list` antes de publicar, por lo que
su restaurabilidad semántica permanece pendiente de certificación.

El algoritmo y gestión de claves deben ser aprobados por seguridad del cliente.
Para despliegues regulados puede requerirse envelope encryption, HSM/KMS,
rotación, custodia dual o un formato distinto.

El HMAC no protege contra borrado ni replay de un respaldo antiguo válido. El
compromiso de la clave también permite falsificar artefactos. El control se
debe complementar con retención inmutable, versionado, monitoreo, rotación y
custodia externa aprobados por el cliente.

Si la restauración y el rollback fallan, el directorio temporal privado se
conserva como evidencia. Puede incluir el material descifrado y la clave
capturada, por lo que debe permanecer en almacenamiento protegido y someterse a
un procedimiento aprobado de análisis y eliminación.

Límite actual: los scripts de backup y restore requieren `openssl` en el host.
Antes de distribuir el instalador corporativo, esta utilidad debe incorporarse
a una imagen de herramientas fijada por digest para mantener la promesa de no
instalar dependencias nativas manualmente.

## Bloqueadores externos

1. Proveedor de identidad, mapeo de roles y autorización dentro de la aplicación.
2. Proxy/firewall de egress y destinos exactos del plano central.
3. Registry, firma, SBOM, política de vulnerabilidades y digests aprobados.
4. Custodia y rotación de claves; cifrado de volúmenes y temporales.
5. RPO, RTO, retención, ubicación inmutable y eliminación segura.
6. CA corporativa, DNS, renovación y distribución de confianza.
7. Ensayo real de recuperación y rollback con aceptación del cliente.
