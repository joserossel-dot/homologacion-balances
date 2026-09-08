# Control humano previo a producción

Este procedimiento comienza sólo después de que la suite automatizada y la
recertificación privada hayan terminado. No aprueba producción por sí solo.
Cada responsable debe conservar la salida completa, fecha, identidad y versión
evaluada.

## Estado automatizado que habilita este control

Evidencia local del 7 de septiembre de 2026:

- 1.219 pruebas recolectadas; 1.202 aprobadas y 17 omitidas por fixtures privados
  o Gold no disponibles en la suite pública;
- matriz privada básica con 4/4 expectativas aprobadas: 3/3 casos obligatorios
  certificados y Fundación Arte y Solidaridad en estado `parcial`, fuera del
  gate automático hasta confirmar manualmente la fila 19 (`IMPTOS. POR PAGAR`);
- matriz Gold 0/3 rechazada. La reproducción posterior separa 97 filas
  distintas: tres códigos contables y diferencias superpuestas de método o
  confianza. No son 97 reclasificaciones humanas pendientes. Véase
  `GOLD_PENDIENTES_20260907.md` para el alcance exacto del contrato comparado;
- verificador estático on-premise 37/37 aprobado;
- Tesseract disponible con idioma español y hash del modelo registrado;
- inventario de arquitectura sin bypass TLS y sin entrypoints faltantes;
- auditoría Neon parcialmente verificada mediante transacción de solo lectura:
  469 validaciones y dos revisores; no existe la fuente completa de estados
  de la cola. Las validaciones no acreditan candidatos pendientes ni aprobaciones;
- smoke Docker real no ejecutado porque el daemon local no está disponible.

Este estado es `NO-GO` para producción hasta completar las secciones 2 a 9 de
este documento.

## 1. Identificar exactamente el candidato

Responsable: release manager.

Desde la raíz del repositorio:

```bash
git status --short --branch
git rev-parse --show-toplevel
git rev-parse HEAD
git remote -v
git diff --check
```

Criterio de aceptación:

- la rama y el commit corresponden al candidato acordado;
- no existen archivos locales ajenos al candidato;
- no se continúa desde un commit distinto al certificado;
- el resultado se adjunta al acta de release.

## 2. Ejecutar el ciclo Docker real en un ambiente aislado

Responsable: administrador de plataforma.

Prerrequisitos: Docker Desktop o Docker Engine activo, al menos 10 GB libres y
ninguna instalación productiva usando los puertos 18080 o 18443.

```bash
docker info
deployment/onprem/scripts/verify-package.sh
deployment/onprem/scripts/smoke-test.sh
```

El smoke crea un proyecto efímero. En evaluación construye la imagen y prueba
bootstrap, HTTPS con CA local explícita, persistencia tras reinicio, respaldo
cifrado, restauración y recuperación de salud. El mensaje de éxito esperado es:

```text
SMOKE ON-PREMISE (evaluation): APROBADO; CA local explícita y backup cifrado. Identidad corporativa pendiente de aceptación separada.
```

Si falla, repetir una sola vez con evidencia conservada:

```bash
KEEP_ONPREM_SMOKE_ARTIFACTS=true deployment/onprem/scripts/smoke-test.sh
```

No convertir una segunda falla en aprobación manual. Adjuntar los logs y la
ruta de artefactos al hallazgo.

Para probar las imágenes fijadas por digest utilizar `ONPREM_SMOKE_MODE=production`
con los prerrequisitos de `DOCKER_PENDIENTES_20260907.md`. Ese modo no construye
la imagen y exige el preflight de producción. La CA del smoke sigue siendo
local al proyecto: la CA corporativa, las rutas autenticadas, la ausencia de
exposición de la instalación objetivo y el rollback con fallo real requieren
evidencias separadas. El daemon local no estaba disponible en la última revisión.

## 3. Fijar y aprobar las imágenes por digest

Responsable: seguridad de plataforma y release manager.

Para cada imagen definida en `deployment/onprem/.env.example`, resolver el
digest de la arquitectura que usará el servidor. Ejemplo:

```bash
docker buildx imagetools inspect python:3.12-slim-bookworm
docker buildx imagetools inspect postgres:16-alpine
docker buildx imagetools inspect caddy:2.8-alpine
docker buildx imagetools inspect alpine:3.20
```

Registrar referencias `imagen@sha256:...` en el gestor de configuración. No
copiar tags mutables a producción. Ejecutar el preflight con las cuatro
referencias, `AUTH_ENFORCEMENT=forward_auth`, Caddy de producción y respaldo
cifrado:

```bash
cd deployment/onprem
ONPREM_DEPLOYMENT_MODE=production \
AUTH_ENFORCEMENT=forward_auth \
CADDYFILE_PATH=./Caddyfile.production \
BACKUP_ENCRYPTION_REQUIRED=true \
APP_IMAGE_REFERENCE='REEMPLAZAR@sha256:REEMPLAZAR' \
POSTGRES_IMAGE='REEMPLAZAR@sha256:REEMPLAZAR' \
CADDY_IMAGE='REEMPLAZAR@sha256:REEMPLAZAR' \
CADDY_INIT_IMAGE='REEMPLAZAR@sha256:REEMPLAZAR' \
python3 preflight.py
```

Criterio de aceptación: salida sin error, digests registrados, SBOM y escaneo
de vulnerabilidades asociados al mismo digest. La aceptación de
vulnerabilidades requiere responsable y vencimiento; no se acepta sólo porque
la imagen arranque.

## 4. Elegir e integrar identidad corporativa

Responsables: seguridad del cliente y dueño funcional.

Completar por escrito:

1. Proveedor: OIDC, Active Directory u otro gateway corporativo.
2. Claim inmutable que se mapeará a `actor_id`.
3. Claim de organización que se mapeará a `organization_id`.
4. Grupos exactos para `analyst`, `supervisor` y `admin`.
5. MFA exigido a supervisor y administrador.
6. Duración de sesión, revocación y procedimiento break-glass.
7. Responsables autorizados para altas y bajas.

Pruebas obligatorias:

- sin identidad, la aplicación bloquea el acceso;
- analista no puede promover diccionario ni ejecutar rollback;
- supervisor puede revisar y promover, pero no administrar secretos;
- administrador puede operar rollback y configuración;
- una organización no puede leer decisiones, documentos ni auditoría de otra;
- cada corrección y promoción conserva actor, organización, fecha y roles.

Guardar capturas y eventos de auditoría de cada caso. No usar una cuenta
compartida para esta validación.

## 5. Revisar candidatos Gold sin aprobación automática

Responsables: dos analistas contables, con un supervisor para desempate.

La revisión humana ya recibida debe conservarse. El 7 de septiembre el usuario
confirmó alcance global para las tres decisiones: AC.08, PNC.05 y ER.04 según
las etiquetas de `POLITICA_GLOBAL_CLASIFICACION_20260907.md`. No volver a pedir
esa decisión. Las diferencias de método y confianza requieren revisión de
procedencia con evidencia técnica y referencia versionada. Cosemar y Purefruit
superaron la certificación técnica integrada; ABS conserva estado parcial.
Gold completo permanece 0/3. Véase la sección más reciente de
`GOLD_PENDIENTES_20260907.md` antes de usar las cifras históricas de este documento.

Antes de revisar Gold, cerrar el control OCR de
`fundacion_arte_solidaridad_2024.pdf`:

1. Abrir la página 1 a escala legible.
2. Ubicar la fila `IMPTOS. POR PAGAR`.
3. Confirmar que Débito sea `495.556`, Crédito `2.612.666`, Saldo acreedor
   `2.117.110` y Pasivo `2.117.110`.
4. Corregir el Crédito. El sistema conserva como trazabilidad que OCR leyó
   `2.612.606` y que el subtotal sólo permitía derivar `2.612.664`.
5. Recertificar el contenido corregido. No aceptar como definitivo un valor
   derivado únicamente porque esté dentro de la tolerancia.

Para cada caso obligatorio del manifiesto privado:

1. Abrir el PDF fuente y el candidato Gold lado a lado.
2. Verificar cuenta, código, monto, período, moneda, columna de origen, método y
   confianza.
3. Verificar subtotales impresos, total activo, pasivo más patrimonio y resultado.
4. Marcar discrepancias; no corregir el PDF ni relajar la expectativa para que
   la prueba pase.
5. Registrar analista, fecha y motivo por fila modificada.
6. Reejecutar la matriz Gold y exigir aprobación exacta de todos los casos
   obligatorios.

Los casos `partial`, `failed` y `non_evaluable` no equivalen a certificados.
Un documento ilegible puede quedar no evaluable, pero no debe convertirse en
Gold mediante inferencia.

## 6. Verificar la cola y aprobar la política de promoción

Responsables: supervisor funcional y administrador de base de datos.

La cola no debe estimarse desde `log_validaciones`. Para medirla en Neon se
requiere una vista de sólo lectura `public.promotion_backlog_audit_v1` con
`status`, `created_at` y `reviewer_id`, y una cuenta con privilegio `SELECT`
exclusivo sobre esa vista.

```bash
DATABASE_URL='URL_READ_ONLY' python3 scripts/audit_promotion_backlog.py --require-verified
```

Guardar sólo el JSON agregado. No adjuntar URL, nombres de cuentas, montos ni
identificadores de revisores.

Decisiones que deben quedar aprobadas:

- promoción manual por supervisor;
- evidencia mínima obligatoria;
- cero conflictos abiertos;
- vigencia predeterminada y revisión al expirar;
- rollback asociado al registro original;
- prohibición de actores genéricos o texto libre como supervisor.

## 7. Aprobar operación, datos y recuperación

Responsables: dueño de datos, seguridad y continuidad operacional.

Completar y firmar:

- campos de telemetría permitidos y prohibidos;
- retención de documentos, temporales, auditoría y respaldos;
- custodia y rotación de claves de respaldo;
- CA corporativa y distribución de confianza a estaciones autorizadas;
- allow-list de salida hacia el plano central;
- RPO y RTO contractuales;
- frecuencia de prueba de restore y responsable de ejecución;
- procedimiento de actualización y rollback.

Ejecutar un restore con respaldo cifrado en un ambiente no productivo y medir
los tiempos reales. Si exceden RPO/RTO, el control queda rechazado aunque el
restore termine.

Antes del restore, ejecutar el escaneo de sólo lectura del runtime instalado:

```bash
python3 scripts/reconcile_local_runtime.py \
  --root /RUTA/ABSOLUTA/AL/RUNTIME scan
```

La salida debe ser JSON agregado. No debe crear `operations.db`, cambiar hashes,
mover archivos ni incluir nombres de cuentas o montos. Si aparecen hallazgos,
conservar la salida y ejecutar cuarentena únicamente con un administrador
identificado y la confirmación literal exigida por `--help`. No existe una
operación de borrado definitivo. Después de corregir la causa, probar `restore`
en el ambiente no productivo y volver a ejecutar `scan`.

## 8. Confirmar consumidores externos antes de podar módulos

Responsable: líder técnico.

Buscar jobs, notebooks, cron, integraciones y scripts externos que importen:

- `learning.statistics`;
- `pipeline.new_pipeline`;
- `semantic.semantic_catalog`;
- `src.api`.

Responder por cada módulo: `usado`, `no usado` o `no verificado`, incluyendo
evidencia. Sólo los marcados `no usado` con evidencia pueden eliminarse. La
ausencia de imports dentro de este repositorio no demuestra por sí sola que no
exista un consumidor externo.

## 9. Decisión final

Participantes mínimos: dueño funcional, seguridad, plataforma, release manager
y supervisor contable.

La decisión debe contener:

- commit e imágenes exactas;
- resultados completos de suite, corpus, Gold y smoke;
- controles humanos aprobados y responsables;
- riesgos aceptados con vencimiento;
- rollback probado;
- decisión `GO`, `NO-GO` o `PILOTO CONTROLADO`.

Un estado `NO-GO` no autoriza commit, push, despliegue ni modificación de Gold.

## Orden recomendado para reducir retrabajo

1. Confirmar la fila 19 de Fundación Arte y Solidaridad contra el PDF.
2. Revisar las 97 discrepancias Gold entre dos analistas.
3. Elegir proveedor de identidad y mapear claims a actor, organización y roles.
4. Ejecutar el ciclo Docker completo con esas identidades y guardar evidencias.
5. Medir la cola de promociones mediante la vista Neon agregada de sólo lectura.
6. Confirmar consumidores externos de los cuatro módulos pendientes de poda.
7. Aprobar RPO, RTO, retención, CA, claves, digests, SBOM y allow-list.
8. Repetir suite, matriz básica y Gold sobre el commit exacto candidato.
9. Firmar la atestación Ed25519 y emitir el acta final `GO`, `NO-GO` o
   `PILOTO CONTROLADO`.
