#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
project_root="$(CDPATH= cd -- "${compose_dir}/../.." && pwd)"
mode="${ONPREM_SMOKE_MODE:-evaluation}"
for dependency in docker python3 curl openssl; do
    command -v "$dependency" >/dev/null 2>&1 || {
        echo "BLOQUEADO: falta $dependency." >&2; exit 69;
    }
done
case "$mode" in
    evaluation) export CADDYFILE_PATH=./Caddyfile;;
    production)
        export CADDYFILE_PATH=./Caddyfile.production
        export AUTH_ENFORCEMENT=forward_auth
        PERSISTENCE_MODE=local LOCAL_PERSISTENCE_ROOT=/var/lib/homologacion/runtime \
        ONPREM_DEPLOYMENT_MODE=production BACKUP_ENCRYPTION_REQUIRED=true \
        PYTHONPATH="$project_root" python3 -c \
            'from deployment.onprem.preflight import validate; validate()'
        ;;
    *) echo "ONPREM_SMOKE_MODE debe ser evaluation o production." >&2; exit 64;;
esac
if ! docker info >/dev/null 2>&1; then
    echo "BLOQUEADO: daemon Docker no disponible." >&2
    exit 69
fi
umask 077
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/homologacion-onprem-smoke.XXXXXX")"
project_name="homologacion-smoke-$$"
http_port="${ONPREM_SMOKE_HTTP_PORT:-18080}"
https_port="${ONPREM_SMOKE_HTTPS_PORT:-18443}"
env_file="${run_dir}/smoke.env"
backup_dir="${run_dir}/backups"
export COMPOSE_PROJECT_NAME="${project_name}"
export ONPREM_DEPLOYMENT_MODE="$mode"
export BACKUP_ENCRYPTION_REQUIRED=true
export ONPREM_COMPOSE_ENV_FILE="${env_file}"
if [ "$mode" = evaluation ]; then
    export ONPREM_COMPOSE_OVERRIDE="${compose_dir}/docker-compose.evaluation.yml"
else
    export ONPREM_COMPOSE_OVERRIDE=""
fi
. "$script_dir/compose-context.sh"

cleanup() {
    if [ -f "$env_file" ]; then
        compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
    if [ "${KEEP_ONPREM_SMOKE_ARTIFACTS:-false}" != "true" ]; then
        find "${run_dir}" -type f -exec sh -c 'for item do : > "$item"; done' sh {} +
        find "${run_dir}" -depth -delete
    else
        echo "Artefactos conservados en: ${run_dir}"
    fi
}
trap cleanup EXIT HUP INT TERM

{
    echo "COMPOSE_PROJECT_NAME=${project_name}"
    echo "APP_IMAGE_REFERENCE=${APP_IMAGE_REFERENCE:-homologacion-balances:smoke-local}"
    echo "APP_RELEASE_BRANCH=onprem-smoke"
    echo "APP_BUILD_DATE=smoke-test"
    echo "POSTGRES_DB=homologacion"
    echo "POSTGRES_USER=homologacion_app"
    echo "CADDY_HOSTNAME=localhost"
    echo "HTTP_PORT=${http_port}"
    echo "HTTPS_PORT=${https_port}"
    echo "MAX_UPLOAD_MB=10"
    echo "QUALITY_CONTROL_ENFORCE_EXPORT=true"
    echo "CADDYFILE_PATH=${CADDYFILE_PATH}"
} > "${env_file}"

export BACKUP_ENCRYPTION_KEY_FILE="${run_dir}/backup.key"
openssl rand -hex 32 > "$BACKUP_ENCRYPTION_KEY_FILE"
export BACKUP_DIR="${backup_dir}"

echo "1/8 Validando configuracion Compose"
compose config --quiet

echo "2/8 Construyendo e iniciando instalacion aislada"
if [ "$mode" = evaluation ]; then
    compose up --build --detach --wait
else
    compose up --detach --wait
fi

echo "3/8 Verificando salud HTTPS"
# Trust only the CA obtained from this isolated project's Caddy volume.
ca_file="${run_dir}/smoke-root.crt"
compose cp reverse-proxy:/data/caddy/pki/authorities/local/root.crt "$ca_file"
test -s "$ca_file"
curl --fail --silent --show-error --cacert "$ca_file" \
    --resolve "localhost:${https_port}:127.0.0.1" \
    "https://localhost:${https_port}/_stcore/health" | grep -q '^ok$'

echo "4/8 Verificando persistencia realmente consumida por la aplicacion"
probe="$(compose exec -T app python deployment/onprem/persistence_probe.py --write-marker)"
printf '%s' "${probe}" | python3 -c \
    'import json,sys; x=json.load(sys.stdin); assert x["mode"] == "local"; assert x["operational_enabled"]; assert all(x["repositories"].values()); assert x["audit_markers"] >= 1'

echo "5/8 Verificando durabilidad despues de reiniciar la aplicacion"
compose restart app >/dev/null
probe="$(compose exec -T app python deployment/onprem/persistence_probe.py)"
printf '%s' "${probe}" | python3 -c \
    'import json,sys; x=json.load(sys.stdin); assert x["audit_markers"] >= 1; assert x["knowledge_healthy"]'

echo "6/8 Verificando backup de app_runtime"
compose exec -T app sh -eu -c \
    'printf original > /var/lib/homologacion/runtime/smoke-restore-marker'
sh "${script_dir}/backup-runtime.sh" >/dev/null
backup_file="$(find "$backup_dir" -type f -name '*.tar.gz.enc' -print | head -n 1)"
test -n "$backup_file" && test -s "$backup_file" && test -s "$backup_file.sha256"

echo "7/8 Verificando restore de app_runtime"
compose exec -T app sh -eu -c \
    'printf alterado > /var/lib/homologacion/runtime/smoke-restore-marker'
sh "${script_dir}/restore-runtime.sh" "$backup_file" --confirm >/dev/null
restored="$(compose exec -T app cat /var/lib/homologacion/runtime/smoke-restore-marker)"
test "$restored" = original

echo "8/8 Verificando recuperacion de salud"
attempt=0
until curl --fail --silent --cacert "$ca_file" \
    --resolve "localhost:${https_port}:127.0.0.1" \
    "https://localhost:${https_port}/_stcore/health" | grep -q '^ok$'; do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge 30 ]; then
        echo "FALLO: la aplicacion no recupero salud tras reinicio." >&2
        exit 1
    fi
    sleep 2
done

echo "SMOKE ON-PREMISE ($mode): APROBADO; CA local explícita y backup cifrado. Identidad corporativa pendiente de aceptación separada."
