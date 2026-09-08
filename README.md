# Plataforma de Homologación de Balances Tributarios Chilenos

Transforma balances tributarios chilenos en PDF o Excel en estados financieros
normalizados para revisión humana y análisis de riesgo crediticio.

## Flujo operativo actual

- entrada principal: `streamlit run app_validacion.py`;
- extracción: `parser_universal.py` y extractores documentales auxiliares;
- homologación: `pipeline/homologation_pipeline.py`;
- conocimiento remoto heredado: `persistence/neon_store.py`;
- persistencia desacoplada en adopción: contratos y factoría bajo `persistence/`;
- validación y certificación: módulos `validation/`, controles de integridad y
  pruebas de corpus.

La API FastAPI experimental y su repositorio PostgreSQL paralelo fueron
retirados porque no formaban parte del despliegue Streamlit, usaban otro esquema
y contenían una conexión TLS sin verificación. La API central prevista para el
modelo on-premise todavía no está implementada.

## Requisitos de desarrollo

- Python 3.12;
- Poetry;
- Tesseract OCR con idioma español;
- Poppler;
- PostgreSQL sólo cuando se prueba el adaptador remoto heredado.

## Instalación local

```bash
poetry install
poetry run streamlit run app_validacion.py
```

No cree usuarios ni contraseñas con valores publicados en el repositorio. Para
usar PostgreSQL, entregue `DATABASE_URL` mediante el gestor de secretos del
entorno y una cuenta de privilegio mínimo. No guarde `.env`, certificados,
claves ni dumps dentro del repositorio.

## Preflight seguro

Antes de ejecutar contra Neon o PostgreSQL remoto:

```bash
export DATABASE_URL='<inyectada por el gestor de secretos>'
poetry run python scripts/neon_preflight.py
```

La cadena remota debe exigir TLS conforme a la política del proveedor y del
cliente. No se admite desactivar la verificación de certificados. La CA, la
rotación de credenciales y el mecanismo exacto de autenticación son decisiones
del despliegue corporativo.

Para trabajar sin red con los adaptadores locales:

```bash
export PERSISTENCE_MODE=local
export LOCAL_PERSISTENCE_ROOT="$PWD/.local-runtime"
poetry run pytest -q tests/persistence
```

`.local-runtime` es sólo un ejemplo de desarrollo. En on-premise debe apuntar a
un volumen persistente fuera del checkout y aplicar las políticas aprobadas de
cifrado, respaldo y retención.

## Paquete on-premise candidato

El prototipo y su verificador están en `deployment/onprem/`. Antes de construir
o levantar el perfil productivo:

```bash
python3 deployment/onprem/preflight.py --environment production
```

El preflight deniega configuraciones sin autenticación externa, secretos de
ejemplo, imágenes mutables o backup cifrado. Docker Compose por sí solo no
impone una política completa de egress del host; ese control requiere firewall
o plataforma de red administrada.

## Estructura relevante

```text
app_validacion.py                 interfaz Streamlit y flujo principal
parser_universal.py               extracción PDF, OCR y Excel
pipeline/homologation_pipeline.py homologación operativa
persistence/neon_store.py         adaptador remoto heredado
persistence/contracts/            puertos locales y clientes remotos
persistence/local/                adaptadores de archivos, JSON y SQLite
persistence/factory.py            selección explícita legacy_neon o local
validation/                        reglas de validación y certificación
deployment/onprem/                prototipo de despliegue corporativo
docs/architecture/                decisiones, inventario y migración
```

## Identidad y auditoría

`persistence/contracts/identity.py` define roles `analyst`, `supervisor` y
`admin`, además de propagación obligatoria del actor a auditoría. El proveedor
de identidad no está seleccionado. El adaptador predeterminado deniega toda
autenticación; no confía en cabeceras aportadas por el cliente.

## Estado y límites

- El flujo Streamlit aún instancia directamente `NeonKnowledgeStore`; la
  factoría desacoplada todavía debe integrarse en consumidores operativos.
- Los adaptadores locales actuales sirven para desarrollo o una instalación
  individual; SQLite no es la base objetivo multiusuario.
- No existe todavía una API central productiva de licencia, paquetes maestros o
  telemetría.
- Los balances reales, secretos y respaldos no se incluyen en el repositorio.

Consulte `docs/architecture/module_inventory.md`,
`docs/architecture/persistence_refactor.md` y
`docs/architecture/on_premise_target.md` antes de una decisión de producción.
