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
El respaldo incluye checksum del archivo cifrado y metadatos de RPO, RTO,
retención, formato y fecha. La retención elimina artefactos más antiguos dentro
del directorio de backup explícito.

`restore-runtime.sh` verifica checksum, metadatos, manifiesto cerrado, hashes por
archivo, JSON e integridad SQLite antes de detener servicios. Extrae en staging,
crea un respaldo previo cifrado y, si falla la sonda posterior al reemplazo,
recupera el snapshot anterior. Las pruebas sin daemon cubren round-trip,
traversal, alteración de manifiesto, cifrado y conservación ante archivo inválido.
Falta ejecutar el mismo ciclo contra un volumen Docker y storage reales.

`backup.sh` y `restore.sh` permanecen únicamente para el perfil explícito
`legacy-postgres`; no protegen la persistencia operativa de la UI local.

El algoritmo y gestión de claves deben ser aprobados por seguridad del cliente.
Para despliegues regulados puede requerirse envelope encryption, HSM/KMS,
rotación, custodia dual o un formato distinto.

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
