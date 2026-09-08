# Arquitectura objetivo on-premise

## Estado del documento

Diseño objetivo y prototipo inicial. No constituye autorización de producción.
Las funciones marcadas como pendientes no están implementadas por el paquete
`deployment/onprem`.

## Principios

1. PDF, Excel, texto OCR, nombres de cuentas, RUT, montos, reportes y decisiones
   contables permanecen dentro de la infraestructura del cliente.
2. La base de datos local no publica puertos y nunca acepta conexiones desde la
   nube.
3. El nodo local sólo inicia conexiones HTTPS salientes hacia destinos
   explícitamente autorizados.
4. La API central es un plano de control. No procesa balances ni consulta la
   base local.
5. Una indisponibilidad temporal de internet no debe detener inmediatamente la
   operación autorizada del cliente.

## Topología objetivo

```text
Usuarios corporativos
        |
     HTTPS
        |
Reverse proxy local
        |
Aplicación Streamlit ---- OCR síncrono actual
        |
        +---------- volumen app_runtime
                    |-- JSON conocimiento
                    |-- SQLite operacional
                    `-- documentos y reportes
        |
        +-- HTTPS saliente --> API central
                               |-- licencias
                               |-- paquetes maestros firmados
                               `-- telemetría mínima
```

### Plano local

Responsable de:

- recepción y selección de páginas;
- parser PDF y Excel;
- Tesseract y Poppler;
- clasificación, revisión humana y cuadratura;
- generación y conservación de reportes;
- usuarios, roles y auditoría;
- catálogo y diccionario activos;
- respaldo, restauración y retención.

### Plano central

Responsable exclusivamente de:

- organizaciones, contratos, licencias y nodos autorizados;
- versiones compatibles de software;
- publicación y revocación de paquetes maestros;
- telemetría técnica agregada y auditada.

Neon puede almacenar el plano central. No debe almacenar documentos ni datos
contables del cliente sin una base contractual y técnica específica.

### Superficie mínima de la API central

```text
POST /v1/nodes/activate
POST /v1/licenses/renew
GET  /v1/master-bundles/latest?channel=stable
GET  /v1/master-bundles/{version}/manifest
GET  /v1/master-bundles/{version}/download
POST /v1/telemetry/events
```

Los endpoints de activación y renovación identifican organización, nodo y
versión, pero no reciben datos del documento. La descarga de paquetes debe usar
URLs de corta duración y el nodo valida la firma después de descargar. La
telemetría usa eventos tipados con esquema cerrado, tamaño máximo y rechazo de
propiedades adicionales.

## Contrato de datos nodo-nube

### Datos permitidos

- identificador pseudónimo de organización y nodo;
- versión de aplicación, catálogo, diccionario y reglas;
- estado y vencimiento de licencia;
- duración total y por etapa;
- cantidad de páginas, cuentas y revisiones;
- indicador de uso de OCR;
- códigos de error técnicos normalizados;
- resultado de actualización o rollback.

### Datos prohibidos

- archivos PDF, Excel o imágenes;
- texto nativo u OCR;
- RUT, razón social, nombres de personas o empresas;
- nombres o códigos originales de cuentas;
- montos, períodos y resultados financieros;
- reportes y decisiones contables detalladas;
- credenciales o cadenas de conexión locales;
- muestras de documentos en logs o trazas.

La API debe validar un esquema cerrado y rechazar campos desconocidos. La
ausencia de un campo sensible no puede depender sólo de la disciplina del nodo.

Ejemplo de evento permitido:

```json
{
  "schema_version": 1,
  "organization_id": "org_pseudonima",
  "node_id": "nodo_pseudonimo",
  "event_type": "processing_completed",
  "application_version": "1.0.0",
  "master_bundle_version": "2026.08.1",
  "metrics": {
    "pages": 3,
    "accounts": 72,
    "ocr_used": false,
    "manual_reviews": 4,
    "duration_ms": 18040
  }
}
```

No se permiten extensiones libres, texto de errores sin normalizar ni nombres
de archivos. Los errores deben representarse mediante códigos previamente
publicados.

## Licencia offline con gracia

Flujo objetivo:

1. El nodo se autentica con una credencial única y revocable.
2. La API entrega un documento de licencia firmado, con organización, nodo,
   capacidades, emisión, vencimiento y período de gracia.
3. El nodo valida localmente la firma con una clave pública incorporada.
4. La renovación se intenta periódicamente con retroceso exponencial.
5. Durante la gracia se permiten nuevos procesos y se registra la condición.
6. Terminada la gracia se bloquean procesos nuevos, pero se permite consultar y
   descargar trabajos anteriores.

Decisiones pendientes:

- duración de la licencia y de la gracia;
- mecanismo de revocación para nodos desconectados;
- política especial para instalaciones sin salida a internet;
- protección del reloj local y tolerancia a desfases.

## Paquetes maestros firmados

Cada paquete debe ser inmutable e incluir:

- catálogo, diccionario y reglas;
- versión y fecha;
- versión mínima y máxima compatible de la aplicación;
- manifiesto de archivos con SHA-256;
- firma digital del manifiesto;
- migraciones y notas de versión.

El nodo debe verificar firma, hashes y compatibilidad antes de activar el
paquete. Debe conservar como mínimo la versión activa y la anterior, registrar
quién aprobó la activación y poder ejecutar rollback sin acceso a internet.

## Persistencia local

La refactorización debe separar:

```text
LocalDocumentRepository
LocalExecutionRepository
LocalKnowledgeRepository
LocalAuditRepository
LocalUserRepository
ReportRepository
LicenseClient
MasterDataClient
TelemetryClient
```

El Compose actual configura `PERSISTENCE_MODE=local`. El bundle construido por
preflight, bootstrap y la sonda usa
JSON para catálogo y diccionario, SQLite para ejecuciones, auditoría, usuarios y
metadata de promociones, y filesystem para documentos y reportes, todo dentro
de `app_runtime`. El PostgreSQL declarado queda aislado bajo el perfil opcional
`legacy-postgres` y no es consumido por `bootstrap`. La prueba integral de la UI
debe confirmar que no queda ningún acceso heredado directo que eluda el bundle.

## Worker OCR

No se incluye un worker falso en el prototipo. Para incorporarlo deben existir:

1. tabla o broker de trabajos con estados y leases;
2. payload que contenga sólo una referencia local al documento;
3. idempotencia por hash, página y versión del extractor;
4. reintentos limitados y cola de fallas;
5. cancelación, progreso y timeout por página;
6. limpieza segura de temporales;
7. recuperación tras reinicio.

Hasta completar estos puntos, OCR continúa síncrono en el servicio `app`.

## Controles del prototipo

- aplicación y proxy ejecutados con UID no-root;
- PostgreSQL heredado sólo en perfil explícito y red interna;
- único ingreso a través de HTTPS;
- XSRF habilitado y tamaño de carga configurable;
- secreto PostgreSQL fuera de `.env` y de Git;
- healthchecks y dependencias de arranque;
- límites de CPU y memoria;
- bootstrap no destructivo: sólo inserta maestros ausentes, conserva conflictos
  y registra versión y checksum del paquete aplicado;
- volúmenes persistentes para PostgreSQL y Caddy;
- bloqueo de exportación crítica activado por defecto.
- filesystem de aplicación de sólo lectura: el fallback sobre JSON empaquetado
  queda bloqueado y la única ruta de conocimiento es el JSON durable del volumen;
- contexto Docker excluye secretos, volcados, respaldos, bases locales, llaves y
  credenciales;
- restore de `app_runtime` exige checksum y manifiesto, valida staging, detiene
  aplicación y proxy, crea un respaldo previo y revierte ante falla posterior;
- `forward_auth` provider-neutral y denegación predeterminada en producción;
- redes de aplicación, datos y proxy marcadas como internas, sin egress general;
- preflight que rechaza referencias de imagen sin digest en producción;
- respaldo cifrado obligatorio en producción mediante clave externa, con
  retención y metadatos RPO/RTO configurables.

## Backup y restore

El respaldo operativo cubre `app_runtime`. La herramienta genera una copia
SQLite mediante la API de backup, excluye WAL/SHM, incorpora un manifiesto con
SHA-256 y tamaño de cada archivo, y valida JSON e integridad SQLite antes de
restaurar. En Docker, el reemplazo del contenido del volumen no es atómico porque
Compose no renombra volúmenes; el procedimiento es fail-safe: valida staging,
preserva un snapshot previo y lo reaplica si falla la sonda posterior.

`backup.sh` y `restore.sh` cubren sólo el PostgreSQL del perfil heredado. Falta
ejecutar el ciclo runtime con daemon y almacenamiento reales antes de producción.

Antes de producción se debe:

- aprobar algoritmo, custodia y rotación de la clave del cliente;
- enviarlos a almacenamiento separado e inmutable;
- definir RPO, RTO y retención;
- respaldar también documentos y reportes cuando existan sus repositorios;
- ejecutar una restauración completa en un servidor limpio;
- registrar resultado, duración y responsable del ensayo.

## Decisiones pendientes de aprobación

1. PostgreSQL único por instalación o esquema por organización.
2. OIDC/Active Directory versus cuentas locales.
3. Proveedor de certificados y nombres DNS internos.
4. Política de salida a internet y modo totalmente desconectado.
5. RPO, RTO, retención y eliminación segura.
6. Cola PostgreSQL, Redis u otro broker para OCR.
7. Cifrado de volúmenes y respaldos según plataforma del cliente.
8. Campos exactos y retención de telemetría.
9. Duración de licencia y período de gracia.
10. Proceso de firma, aprobación y publicación de paquetes maestros.

Estas decisiones son bloqueadores de producción. El hook `forward_auth` no
selecciona proveedor ni implementa autorización dentro de Streamlit. Las redes
internas niegan egress general, pero Compose no expresa una allow-list por FQDN.
El cifrado de backup no resuelve cifrado de volumen, custodia de claves ni
retención externa. CA, RPO/RTO y digests concretos requieren aprobación.

`master_seed_history` se crea mediante la migración versionada
`persistence/migrations/002_master_seed_history.sql`, aplicada explícitamente
antes del seed.

## Puertas de avance

### Prototipo técnico

- `docker compose config` válido;
- inicio en un servidor limpio; pendiente de ejecutar con daemon Docker activo;
- servicios saludables; pendiente de ejecutar con daemon Docker activo;
- aplicación sin conexión a Neon;
- base no accesible desde el host; validado en configuración, pendiente en runtime;
- respaldo y restauración ensayados; checksum, mantenimiento, respaldo previo y
  staging validados estáticamente, pendiente el ciclo runtime con daemon.

La prueba `deployment/onprem/scripts/smoke-test.sh` convierte estas verificaciones
pendientes en un único ciclo aislado y repetible. El 29 de agosto de 2026 no se
pudo ejecutar porque Docker CLI no encontró el daemon en
`unix:///Users/josealfonsorossel/.docker/run/docker.sock`.

### Piloto controlado

- autenticación y roles;
- repositorios durables y trazabilidad;
- licencia firmada con prueba offline;
- paquete maestro firmado con rollback;
- escaneo de imágenes;
- restauración completa aprobada;
- matriz documental y seguridad aceptadas.

### Producción

- todas las decisiones pendientes cerradas;
- imágenes fijadas por digest;
- runbooks y monitoreo operativo;
- aceptación del cliente;
- evidencia de recuperación, actualización y rollback.
