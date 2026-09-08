#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
archive_tool="${compose_dir}/runtime_archive.py"
backup_dir="${BACKUP_DIR:-${compose_dir}/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"
rpo_hours="${BACKUP_RPO_HOURS:-24}"
rto_hours="${BACKUP_RTO_HOURS:-8}"
docker_bin="${DOCKER_BIN:-docker}"
runtime_source="${RUNTIME_SOURCE_DIR:-}"
encrypted=false
host_uid="$(id -u)"
host_gid="$(id -g)"

case "$backup_dir" in ''|/) echo "BACKUP_DIR inseguro." >&2; exit 78;; esac
case "$host_uid:$host_gid" in *[!0-9:]*) echo "UID/GID del operador inválido." >&2; exit 78;; esac
case "$retention_days:$rpo_hours:$rto_hours" in *[!0-9:]*) echo "Retención/RPO/RTO inválido." >&2; exit 78;; esac
[ "$retention_days" -ge 1 ] && [ "$retention_days" -le 3650 ] || exit 78
if [ "$mode" = production ] && [ "$encryption_required" != true ]; then
    echo "Producción exige cifrado de app_runtime." >&2; exit 78
fi
if [ "$encryption_required" = true ] || [ -n "$encryption_key_file" ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    command -v openssl >/dev/null 2>&1 || exit 69
    encrypted=true
fi

umask 077
mkdir -p "$backup_dir"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/homologacion-runtime-backup.XXXXXX")"
snapshot="${work_dir}/runtime"
plain="${work_dir}/app-runtime.tar.gz"
app_was_running=0
proxy_was_running=0
services_stopped=0
completed=0

. "$script_dir/compose-context.sh"
restart_services() {
    restart_failed=0
    if [ "$services_stopped" -eq 1 ]; then
        if [ "$app_was_running" -eq 1 ]; then
            compose start app >/dev/null 2>&1 || restart_failed=1
        fi
        if [ "$proxy_was_running" -eq 1 ]; then
            compose start reverse-proxy >/dev/null 2>&1 || restart_failed=1
        fi
    fi
    [ "$restart_failed" -eq 0 ] || {
        echo "FALLO: no se pudieron reiniciar todos los servicios tras backup." >&2
        return 70
    }
}
cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    restart_services || { [ "$code" -ne 0 ] || code=70; }
    find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
    rm -rf "$work_dir"
    if [ "$completed" -ne 1 ] && [ -n "${target:-}" ]; then
        rm -f "$target" "$target.sha256" "$target.meta.json" "$target.meta.json.sha256"
    fi
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

if [ -n "$runtime_source" ]; then
    snapshot="$runtime_source"
else
    running="$(compose ps --services --filter status=running)"
    printf '%s\n' "$running" | grep -qx app && app_was_running=1 || true
    printf '%s\n' "$running" | grep -qx reverse-proxy && proxy_was_running=1 || true
    services_stopped=1
    compose stop app reverse-proxy >/dev/null
    mkdir -p "$snapshot"
    compose run --rm --no-deps --user 0:0 --entrypoint sh \
        -e "SNAPSHOT_UID=${host_uid}" -e "SNAPSHOT_GID=${host_gid}" \
        -v "$snapshot:/snapshot" app -eu -c \
        'cp -a /var/lib/homologacion/runtime/. /snapshot/; chown -R "${SNAPSHOT_UID}:${SNAPSHOT_GID}" /snapshot'
fi

python3 "$archive_tool" create "$snapshot" "$plain" \
    --rpo-hours "$rpo_hours" --rto-hours "$rto_hours" >/dev/null
suffix=.tar.gz
[ "$encrypted" = false ] || suffix=.tar.gz.enc
target="${backup_dir}/homologacion-app-runtime-${timestamp}-$$${suffix}"
if [ "$encrypted" = true ]; then
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:${encryption_key_file}" -in "$plain" -out "$target"
else
    mv "$plain" "$target"
fi

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1"
    else echo "No se encontró SHA-256." >&2; exit 69
    fi
}
sha256_file "$target" > "$target.sha256"
cat > "$target.meta.json" <<EOF
{"created_at":"${timestamp}","encrypted":${encrypted},"format":"homologacion-app-runtime-v1","retention_days":${retention_days},"rpo_hours":${rpo_hours},"rto_hours":${rto_hours}}
EOF
sha256_file "$target.meta.json" > "$target.meta.json.sha256"
find "$backup_dir" -type f \
    \( -name 'homologacion-app-runtime-*.tar.gz*' -o -name 'homologacion-app-runtime-*.sha256' -o -name 'homologacion-app-runtime-*.meta.json*' \) \
    -mtime "+${retention_days}" -delete
completed=1
restart_services
services_stopped=0
trap - EXIT HUP INT TERM
find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
rm -rf "$work_dir"
echo "Respaldo app_runtime creado: ${target}"
