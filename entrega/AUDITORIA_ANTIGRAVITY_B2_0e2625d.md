# INFORME DE AUDITORÍA TÉCNICA Y DE SEGURIDAD INDEPENDIENTE
## ENCARGO B2: AUDITORÍA DEL CANDIDATO ON-PREMISE (HOMOLOGACIÓN DE BALANCES)

---

## 1. FICHA DE TRAZABILIDAD

- **Proyecto Auditado**: `homologacion-balances`
- **Ruta Local**: `/Users/josealfonsorossel/AI-Projects/homologacion-balances-pendientes-20260826`
- **Repositorio Remoto**: `https://github.com/joserossel-dot/homologacion-balances.git`
- **Rama**: `codex/mejoras-pendientes-20260826`
- **Commit HEAD Exacto Auditado**: `0e2625df513e63263886e54d7cd4edd90dbedb10`
- **Mensaje del Commit**: `fix: completar regresión Docker on-premise`
- **Auditor Independiente**: Antigravity (Advanced Agentic Coding)
- **Fecha y Hora de Auditoría**: `2026-09-08 12:00:00 -03:00`
- **Estado Inicial del Repositorio**:
  - `git status --short --branch`: `## codex/mejoras-pendientes-20260826...origin/codex/mejoras-pendientes-20260826 [ahead 2]`
  - Worktree limpio, 0 modificaciones locales previas a la generación del informe documental, 2 commits por delante del remoto.

---

## 2. RESUMEN EJECUTIVO CORREGIDO

### 2.1 Veredicto Oficial

> [!IMPORTANT]
> **DICTAMEN OFICIAL: APROBADO CON OBSERVACIONES para continuar a controles preproductivos.**
>
> El paquete Docker y su regresión técnica fueron aprobados. Este dictamen no constituye autorización final de producción ni reemplaza Gold, UAT contable, identidad corporativa, validación de red, recuperación operativa y aprobación GO/NO-GO.

### 2.2 Justificación Técnica Acotada a la Evidencia Obtenida

1. **Aprobación de la Suite Automatizada**: La suite de pruebas y las invariantes de código no presentaron fallos ni regresiones en el entorno de ejecución (1.418 pruebas recolectadas en el gate, 1.401 pruebas aprobadas y 49/49 pruebas estáticas del paquete on-premise).
2. **Remediación Verificada de Defectos Docker**: Se constató mediante inspección de imagen y ejecución viva del smoke test en Docker Compose que los tres defectos que motivaron la reapertura fueron solucionados:
   - Inclusión física de las migraciones SQL SQLite en `/app/persistence/local/migrations/`.
   - Exposición HTTPS accesible desde el host (`bind 0.0.0.0` y red `edge`), manteniendo el servicio de aplicación confinado en la red interna (`frontend`).
   - Saneamiento de permisos en la restauración del volumen (`chown -R 10001:10001 /var/lib/homologacion/runtime`).
3. **Higiene de la Imagen**: Se verificó la ausencia de bytecode del host (`__pycache__` y `*.pyc`) en el directorio `/app` del contenedor.
4. **Smoke Test Aprobado en Modo Evaluación**: Las 8 fases de la prueba integral de humo on-premise concluyeron con código de salida `0`, validando el ciclo de vida básico de arranque, comprobación HTTPS con CA local, persistencia local, backup cifrado, restauración de datos y recuperación de salud.

### 2.3 Resumen por Ámbitos Auditados

| Ámbito Auditado | Calificación | Estado de la Evidencia |
| :--- | :---: | :--- |
| **Ámbito 1: Consistencia contable y certificación documental** | **APROBADO CON OBSERVACIONES** | Suite de reglas contables automatizadas aprobada sin regresiones. La certificación Gold sobre balances reales y el UAT contable permanecen como controles independientes fuera del alcance de B2. |
| **Ámbito 2: Empaquetado on-premise y despliegue** | **APROBADO CON OBSERVACIONES** | Empaquetado Docker Compose v2 y regresión técnica aprobados. El modo producción requiere configuración de un Gateway de Identidad corporativo y definición del modelo TLS. |
| **Ámbito 3: Persistencia, auditoría y aislamiento de datos** | **APROBADO CON OBSERVACIONES** | SQLite local en modo WAL validado para un solo nodo. Respaldo cifrado y restauración verificados técnicamente; la custodia de claves y el ejercicio operativo supervisado permanecen como controles humanos. |
| **Ámbito 4: API central, privacidad y telemetría** | **APROBADO CON OBSERVACIONES** | No se requirió Neon ni Render en las pruebas. Servicio `app` restringido a red interna. Esquema de telemetría cerrado en código. La validación dinámica de tráfico saliente permanece como control preproductivo. |

---

## 3. ENTORNO HOST Y ENTORNO DEL CONTENEDOR SEPARADOS

Para evitar ambigüedades respecto a las versiones de ejecución, se documentan de forma explícita y separada los dos entornos que componen la auditoría:

### 3.1 Entorno Host de Auditoría
- **Sistema Operativo**: macOS (Darwin 24.x arm64).
- **Versión de Python en Host**: `Python 3.14.0` (utilizado exclusivamente en el host para ejecutar `pytest`, el gate de recolección y los scripts de prueba del host).
- **Gestor de Contenedores**: Docker Engine `29.5.3` (Docker Desktop, Docker Compose v2).
- **Herramientas Auxiliares**: OpenSSL `3.x`, curl `8.x`, sh / zsh.

### 3.2 Entorno del Contenedor de la Aplicación
- **Imagen Base Docker**: `python:3.12-slim-bookworm` (definida en `deployment/onprem/Dockerfile` mediante `ARG PYTHON_BUILD_IMAGE=python:3.12-slim-bookworm`, salvo sustitución explícita mediante build arg).
- **Versión de Python en Contenedor**: `Python 3.12` (arquitectura Debian Bookworm).
- **Usuario de Ejecución**: No root, UID/GID `10001:10001` (`homologacion`).
- **Sistema de Archivos en Runtime**: `read_only: true` para el rootfs del contenedor, con `/tmp` montado en `tmpfs`.
- **Motor OCR en Contenedor**: Tesseract OCR versión `5.3.0-2`, paquete de idioma español `tesseract-ocr-spa` versión `1:4.1.0-2`.
- **Proxy Inverso**: `caddy:2.8-alpine`, ejecutándose con usuario `10001:10001`.

---

## 4. PRUEBAS EJECUTADAS Y CÓDIGOS DE SALIDA

Se ejecutaron los cuatro comandos de prueba requeridos registrando sus resultados íntegros:

### 4.1 Colección de Pruebas (`scripts/pytest_collection_gate.py`)
- **Comando**: `python3 scripts/pytest_collection_gate.py`
- **Código de Salida**: `0`
- **Resultado**: `1418 tests collected in 3.88s`
- **Diagnóstico**: Colección completa sin errores de sintaxis, importación ni dependencias faltantes en el entorno de pruebas.

### 4.2 Suite Completa de Pruebas (`pytest -q`)
- **Comando**: `python3 -m pytest -q`
- **Código de Salida**: `0`
- **Resultado**: `1401 passed, 17 skipped, 3 warnings in 69.20s (0:01:09)`
- **Fallos**: `0`
- **Advertencias Registradas**: 3 advertencias de tipo `DeprecationWarning` en Pandas por uso de inversión bitwise `~` en booleanos en `tests/test_manual_revision.py`. No alteran los resultados ni provocan fallos de ejecución.
- **Inventario Detallado de las 17 Pruebas Omitidas (Skipped)**:
  Consultado el reporte detallado de motivos de omisión de pytest (`pytest -rs -q`), se obtuvo el siguiente inventario exacto:
  1. `tests/test_document_kb.py:40` (3 pruebas omitidas): `PDF no encontrado: datasets/validacion/BALANCE 2016.pdf`.
  2. `tests/test_document_mining.py:51` (1 prueba omitida): `PDF no encontrado: datasets/validacion/BALANCE 2016.pdf`.
  3. `tests/test_learning_engine.py:155, 160, 165, 170, 175` (5 pruebas omitidas): `gold_standard.db no disponible`.
  4. `tests/test_learning_runtime.py:228` (1 prueba omitida): `gold_standard.db no disponible`.
  5. `tests/test_ui_knowledge_manager.py:143, 159` (2 pruebas omitidas): `gold_standard.db no disponible`.
  6. `tests/test_pending_parser_regressions.py:60, 94` (5 pruebas omitidas): `Defina BALANCE_REAL_TEST_DIR para la matriz privada`.

  *Evaluación de omisiones*: Las omisiones responden a la ausencia deliberada de datasets locales no versionados (PDF de balance 2016), la base externa `gold_standard.db` y la ruta de la matriz privada de balances reales (`BALANCE_REAL_TEST_DIR`). Ninguna de estas omisiones representa un fallo en la suite ejecutada, pero su ejecución y validación sobre el conjunto completo de datos debe quedar inventariada y completarse antes del acta final GO/NO-GO.

### 4.3 Verificación del Paquete On-Premise (`deployment/onprem/scripts/verify-package.sh`)
- **Comando**: `sh deployment/onprem/scripts/verify-package.sh`
- **Código de Salida**: `0`
- **Resultado**:
  ```text
  Validando sintaxis de scripts
  Validando utilidades Python on-premise
  Validando contrato Compose sin usar el daemon
  Ejecutando pruebas estáticas on-premise
  .................................................                        [100%]
  49 passed in 11.25s
  Docker disponible. Puede ejecutar: deployment/onprem/scripts/smoke-test.sh
  ```
- **Diagnóstico**: Sintaxis POSIX de scripts validada, utilidades on-premise validadas y 49 pruebas estáticas de contrato Compose aprobadas.

### 4.4 Prueba Integral de Humo On-Premise (`deployment/onprem/scripts/smoke-test.sh`)
- **Comando**: `set -o pipefail; sh deployment/onprem/scripts/smoke-test.sh 2>&1 | tee /tmp/homologacion-b2-smoke.log`
- **Código de Salida**: `0`
- **Fases Validadas (8/8)**:
  1. *Fase 1/8 - Validación Compose*: `compose config --quiet` exitosa.
  2. *Fase 2/8 - Construcción y Despliegue*: Contenedores `app-volume-init`, `caddy-volume-init`, `bootstrap`, `app` y `reverse-proxy` levantados y alcanzando estado `Healthy`.
  3. *Fase 3/8 - Salud HTTPS*: Verificación exitosa de endpoint `https://localhost:18443/_stcore/health` respondiendo `ok` utilizando el certificado de la CA local emitido por Caddy.
  4. *Fase 4/8 - Persistencia Consumida*: Sonda `persistence_probe.py` confirma `mode=local`, `operational_enabled=True` y registro de marcadores de auditoría.
  5. *Fase 5/8 - Durabilidad tras Reinicio*: Reinicio forzado de `app` comprobando durabilidad de datos y persistencia del conocimiento (`knowledge_healthy=True`).
  6. *Fase 6/8 - Backup Cifrado*: Creación de archivo `.tar.gz.enc` mediante OpenSSL con checksum `.sha256` en directorio temporal.
  7. *Fase 7/8 - Restauración*: Ejecución de `restore-runtime.sh --confirm`, verificando la preservación exacta del archivo testigo (`restored == original`) y la asignación recursiva de permisos al usuario `10001:10001`.
  8. *Fase 8/8 - Recuperación de Salud*: Recuperación de respuesta HTTP 200 en `/_stcore/health` tras el ciclo completo de restauración.
- **Salida Final**: `SMOKE ON-PREMISE (evaluation): APROBADO; CA local explícita y backup cifrado. Identidad corporativa pendiente de aceptación separada.`

---

## 5. EVIDENCIA DE LOS TRES DEFECTOS DOCKER REMEDIADOS

Se comprobó en el commit `0e2625df513e63263886e54d7cd4edd90dbedb10` la corrección de los tres defectos detectados previamente por Codex:

### 5.1 Defecto A: Migraciones SQL SQLite en la Imagen Docker
- **Problema previo**: `.dockerignore` excluía `**/*.sql` omitiendo `persistence/local/migrations/`, lo que impedía a `SqliteOperationalRepository` inicializar el esquema en tiempo de arranque.
- **Corrección**: Se incluyeron en `.dockerignore` las directivas:
  ```dockerignore
  !persistence/migrations/**/*.sql
  !persistence/local/migrations/**/*.sql
  ```
- **Evidencia en Contenedor**:
  ```bash
  docker run --rm --entrypoint sh homologacion-balances:smoke-local -c "find /app/persistence/local/migrations -type f"
  ```
  *Salida verificada*:
  ```text
  /app/persistence/local/migrations/004_promotion_outcomes.sql
  /app/persistence/local/migrations/003_promotion_policy_metadata.sql
  ```

### 5.2 Defecto B: Exposición HTTPS desde el Host con Aplicación Aislada
- **Problema previo**: Caddy no especificaba `bind 0.0.0.0` y solo estaba en la red `frontend` configurada con `internal: true`, impidiendo el ruteo de tráfico desde el host a través del puerto publicado en Docker Desktop.
- **Corrección**:
  1. En `deployment/onprem/Caddyfile` y `deployment/onprem/Caddyfile.production` se incorporó `bind 0.0.0.0` en los bloques HTTP y HTTPS.
  2. En `deployment/onprem/docker-compose.yml` se configuró la red perimetral `edge` conectada al servicio `reverse-proxy`.
  3. El servicio `app` se mantuvo confinado únicamente en la red `frontend` con `internal: true`, sin publicar puertos al host.
- **Evidencia en Ejecución**:
  La Fase 3 del smoke test comprobó que una llamada externa desde el host contra `https://localhost:18443/_stcore/health` (usando la CA local explícita) responde exitosamente `ok`, mientras que el contenedor `app` no expone ningún puerto fuera de la red interna de Docker.

### 5.3 Defecto C: Restauración de Backup con Permisos del Usuario 10001
- **Problema previo**: El contenedor temporal de restauración (ejecutado con usuario root `0:0`) copiaba los archivos conservando la pertenencia original de los ficheros (`cp -a`), dejando la carpeta `/var/lib/homologacion/runtime` inaccesible para el usuario no privilegiado `10001:10001` de la aplicación.
- **Corrección**: En `deployment/onprem/scripts/restore-runtime.sh` se incorporó la reasignación recursiva:
  ```bash
  chown -R 10001:10001 /var/lib/homologacion/runtime
  ```
- **Evidencia en Ejecución**:
  En las fases 6, 7 y 8 del smoke test, tras ejecutar el script de restauración sobre un volumen alterado, el contenedor `app` (UID 10001) inició normalmente, accedió a la base de datos SQLite restaurada y superó el healthcheck de inmediato.

### 5.4 Comprobación Adicional: Ausencia de Bytecode del Host en la Imagen
- **Comprobación**: Se auditó la regla de exclusión de `.dockerignore`:
  ```dockerignore
  **/__pycache__/
  **/*.py[cod]
  ```
- **Evidencia en Contenedor**:
  ```bash
  docker run --rm --entrypoint sh homologacion-balances:smoke-local -c "find /app -name '__pycache__' -o -name '*.pyc'"
  ```
  *Salida verificada*: 0 archivos devueltos (salida completamente limpia).

---

## 6. ALCANCE Y LIMITACIONES DE LA AUDITORÍA B2

Para evitar conclusiones que excedan la evidencia disponible, se definen taxativamente los límites de lo evaluado en esta auditoría:

### 6.1 Alcance Contable
- **Lo verificado**: La suite automatizada de pruebas contables, reglas de parseo, invariantes matemáticas de 8 columnas e IFRS, validación de subtotales jerárquicos y contratos de no-promoción fueron aprobados sin regresiones.
- **Lo NO verificado**: B2 **no** certifica integralmente la exactitud contable de documentos reales de clientes. La certificación contable Gold sobre balances reales o privados permanece como un control independiente que requiere la ejecución de la matriz privada. B2 no reemplaza la validación humana cuenta por cuenta ni el User Acceptance Testing (UAT) contable.

### 6.2 Conexiones Externas y Telemetría
- **Lo verificado**:
  - En la prueba de humo ejecutada no se requirió conexión a bases de datos en la nube como Neon ni a servicios de despliegue como Render.
  - El servicio `app` está conectado únicamente a la red Docker interna `frontend` (`internal: true`).
  - El proxy inverso participa en las redes `edge` (para acceso desde el host) y `frontend` (para comunicación con la aplicación).
  - El contrato de telemetría en código (`persistence/contracts/remote.py`) restringe las métricas permitidas a un esquema numérico cerrado (`_ALLOWED_TELEMETRY_METRICS`).
- **Lo NO verificado**: B2 no constituye por sí solo una prueba dinámica completa de tráfico saliente de red, pruebas de fuga/exfiltración ni pruebas de integración con una API central. La observación del tráfico real en un entorno con monitor de red y la definición de la política corporativa definitiva de telemetría permanecen como controles preproductivos separados.

### 6.3 Aislamiento Multi-RUT y Multi-Organización
- **Lo verificado**: Las pruebas automatizadas verifican que existen reglas lógicas que bloquean la propagación de sugerencias entre RUTs distintos o entre secciones incompatibles (corriente vs. no corriente).
- **Lo NO verificado**: No se ejecutó en B2 una prueba corporativa integral con dos organizaciones reales concurrentes operando con usuarios, documentos y sesiones independientes sobre infraestructura compartida. Si el producto operará bajo un modelo multi-inquilino en producción, dicha prueba permanece como un control pendiente.

---

## 7. HALLAZGOS Y RIESGOS

| ID | Severidad | Descripción | Impacto / Riesgo | Estado y Mitigación |
| :--- | :---: | :--- | :--- | :--- |
| **H-01** | **Informativa** | **Modo producción exige Gateway de Identidad**. En `Caddyfile.production`, el acceso está bloqueado por defecto (`forward_auth` deny) hasta que se declare `AUTH_GATEWAY_URL`. | La aplicación denegará accesos si no se provee el gateway corporativo. | **Comportamiento por diseño**. Impide exposiciones accidentales sin autenticación corporativa. |
| **H-02** | **Informativa** | **Modelo TLS a elección del operador**. `tls internal` es plenamente válido para entornos de evaluación controlada o clientes que distribuyan y confíen en la CA local de Caddy. Para un FQDN corporativo, el operador debe definir la estrategia TLS. | Si no se confía en la CA local o no se instalan certificados institucionales, los navegadores mostrarán advertencia de seguridad. | Corresponde al control de infraestructura del cliente decidir entre CA institucional, ACME corporativo o distribución administrada de la CA local. |
| **H-03** | **Informativa** | **Perfil SQLite para nodo único**. El motor operacional local SQLite en modo WAL está diseñado como perfil operativo para una instalación de un solo nodo. | Si se requiriese escalamiento horizontal con múltiples contenedores escritores concurrentes, SQLite presentaría bloqueos de concurrencia. | La observación de concurrencia no bloquea un despliegue mono-nodo. Debe revisarse otra estrategia (e.g. PostgreSQL) únicamente si se requiere escalamiento distribuido. |
| **H-04** | **Baja** | **Advertencia de compatibilidad futura**. Con pandas 3.0.3 ejecutado sobre Python 3.14, la inversión `~` sobre valores booleanos emite una advertencia de deprecación durante tres pruebas de `test_manual_revision.py`. | La advertencia indica un cambio previsto para Python 3.16 y no altera los resultados de la suite actual. | Deuda técnica menor; reemplazar la negación ambigua por una comparación vectorizada explícita, por ejemplo `df["es_total"].eq(False)`, después de validar el tipo de la columna. |

---

## 8. CONTROLES HUMANOS Y PREPRODUCTIVOS PENDIENTES

Antes de la emisión del acta definitiva de paso a producción (GO/NO-GO), deben completarse los siguientes controles que exceden el marco de la auditoría técnica B2:

1. **Integración con Identidad Corporativa**:
   - Conexión real con el Gateway de Identidad empresarial (Authentik, Keycloak, OAuth2-Proxy).
   - Configuración de las variables `AUTH_GATEWAY_URL` y `AUTH_GATEWAY_VERIFY_PATH`.
   - Verificación de cabeceras autenticadas (`X-Authenticated-User`).
   - Pruebas efectivas de acceso autorizado, denegado y mitigación de suplantación de cabeceras (header spoofing).
2. **Aceptación del Modelo TLS**:
   - Decisión formal del cliente sobre el modelo de certificados: uso de CA institucional, ACME corporativo o distribución administrada de la CA local de Caddy.
3. **Ejercicio Supervisado de Backup y Recuperación Operativa**:
   - Establecimiento de custodia segura y externa de la clave simétrica de cifrado (`BACKUP_ENCRYPTION_KEY_FILE`).
   - Ejecución de un ejercicio operativo supervisado de respaldo y restauración.
   - Registro de RTO (Recovery Time Objective), RPO (Recovery Point Objective), duración del proceso, operador responsable y evidencia documental.
   - Confirmación explícita de lectura y escritura sobre los datos restaurados.
4. **Certificación Contable Gold y UAT**:
   - Ejecución de la matriz de pruebas contables sobre documentos reales o privados (`BALANCE_REAL_TEST_DIR` y `gold_standard.db`).
   - Validación humana contable cuenta por cuenta y aprobación formal del área contable/financiera (UAT).
5. **Observabilidad de Red y Telemetría**:
   - Inspección dinámica del tráfico saliente en la red perimetral para confirmar el aislamiento de red en el entorno corporativo y formalizar la política de telemetría.

---

## 9. DICTAMEN CORREGIDO

> [!IMPORTANT]
> **APROBADO CON OBSERVACIONES para continuar a controles preproductivos. El paquete Docker y su regresión técnica fueron aprobados. Este dictamen no constituye autorización final de producción ni reemplaza Gold, UAT contable, identidad corporativa, validación de red, recuperación operativa y aprobación GO/NO-GO.**

---

## 10. ESTADO GIT ANTES Y DESPUÉS

### 10.1 Estado Antes de la Creación del Informe
```bash
git status --short --branch
# ## codex/mejoras-pendientes-20260826...origin/codex/mejoras-pendientes-20260826 [ahead 2]

git rev-parse HEAD
# 0e2625df513e63263886e54d7cd4edd90dbedb10

git branch --show-current
# codex/mejoras-pendientes-20260826
```
Worktree 100% limpio, sin modificaciones ni archivos untracked.

### 10.2 Estado Después de la Creación del Informe
```bash
git status --short --branch
# ## codex/mejoras-pendientes-20260826...origin/codex/mejoras-pendientes-20260826 [ahead 2]
# ?? entrega/
```
- **Archivos Modificados**: `0`
- **Archivos Nuevos**: Únicamente el archivo documental `entrega/AUDITORIA_ANTIGRAVITY_B2_0e2625d.md`.
- **Acciones Git Ejecutadas**: Cero commits, cero pushes, cero mutaciones a código fuente, configuración, dependencias o infraestructura.
