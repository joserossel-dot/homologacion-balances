#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--confirm" ]; then
    echo "Uso: $0 RUTA_APP_RUNTIME.tar.gz[.enc] --confirm" >&2
    exit 64
fi

source_file="$1"
checksum_file="${source_file}.sha256"
metadata_file="${source_file}.meta.json"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
runtime_target="${RUNTIME_TARGET_DIR:-}"
docker_bin="${DOCKER_BIN:-docker}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
archive_tool="${compose_dir}/runtime_archive.py"
host_uid="$(id -u)"
host_gid="$(id -g)"

[ -s "$source_file" ] && [ -s "$checksum_file" ] || {
    echo "Se requiere respaldo runtime y checksum." >&2; exit 66;
}
case "$host_uid:$host_gid" in *[!0-9:]*) echo "UID/GID del operador inválido." >&2; exit 78;; esac
case "$source_file" in *.enc) encrypted=true;; *) encrypted=false;; esac
if [ "$mode" = production ] && { [ "$encryption_required" != true ] || [ "$encrypted" != true ]; }; then
    echo "Producción exige restore runtime cifrado." >&2; exit 78
fi
if [ "$encrypted" = true ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    command -v openssl >/dev/null 2>&1 || exit 69
fi

sha256_value() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
    else echo "No se encontró SHA-256." >&2; exit 69
    fi
}
verify_checksum() {
    expected="$(awk 'NR == 1 {print $1}' "$2")"
    case "$expected" in *[!0-9a-fA-F]*|'') echo "Checksum inválido." >&2; exit 65;; esac
    [ "${#expected}" -eq 64 ] || { echo "Checksum inválido." >&2; exit 65; }
    actual="$(sha256_value "$1")"
    [ "$(printf '%s' "$expected" | tr 'A-F' 'a-f')" = "$actual" ] || {
        echo "Checksum no coincide; app_runtime no fue modificado." >&2; exit 65;
    }
}
verify_checksum "$source_file" "$checksum_file"
if [ "$mode" = production ]; then
    [ -s "$metadata_file" ] && [ -s "$metadata_file.sha256" ] || {
        echo "Faltan metadatos verificables del respaldo runtime." >&2; exit 66;
    }
    verify_checksum "$metadata_file" "$metadata_file.sha256"
    grep -q '"format":"homologacion-app-runtime-v1"' "$metadata_file" || exit 65
    grep -q '"encrypted":true' "$metadata_file" || exit 78
fi

umask 077
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/homologacion-runtime-restore.XXXXXX")"
plain="${work_dir}/app-runtime.tar.gz"
staging="${work_dir}/staging"
rollback="${work_dir}/rollback"
services_stopped=0
app_was_running=0
proxy_was_running=0
replaced=0

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
        echo "FALLO: no se pudieron reiniciar todos los servicios tras restore." >&2
        return 70
    }
}
replace_volume_from() {
    source="$1"
    compose run --rm --no-deps --user 0:0 --entrypoint sh \
        -v "$source:/replacement:ro" app -eu -c \
        'find /var/lib/homologacion/runtime -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; cp -a /replacement/. /var/lib/homologacion/runtime/; chown -R 10001:10001 /var/lib/homologacion/runtime'
}
cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$code" -ne 0 ] && [ "$replaced" -eq 1 ] && [ -d "$rollback" ]; then
        if ! replace_volume_from "$rollback" >/dev/null 2>&1; then
            echo "FALLO: rollback incompleto. Evidencia preservada en $work_dir" >&2
            restart_services || true
            exit "$code"
        fi
    fi
    restart_services || { [ "$code" -ne 0 ] || code=70; }
    find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
    rm -rf "$work_dir"
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

if [ "$encrypted" = true ]; then
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
        -pass "file:${encryption_key_file}" -in "$source_file" -out "$plain"
else
    cp "$source_file" "$plain"
fi
mkdir -p "$staging"
python3 "$archive_tool" verify "$plain" --extract-to "$staging" >/dev/null

if [ -n "$runtime_target" ]; then
    previous="$(python3 "$archive_tool" restore-local "$plain" "$runtime_target" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("previous") or "")')"
    trap - EXIT HUP INT TERM
    rm -rf "$work_dir"
    echo "Restore app_runtime verificado. Estado anterior: ${previous:-ninguno}"
    exit 0
fi

running="$(compose ps --services --filter status=running)"
printf '%s\n' "$running" | grep -qx app && app_was_running=1 || true
printf '%s\n' "$running" | grep -qx reverse-proxy && proxy_was_running=1 || true
services_stopped=1
compose stop app reverse-proxy >/dev/null
mkdir -p "$rollback"
compose run --rm --no-deps --user 0:0 --entrypoint sh \
    -e "SNAPSHOT_UID=${host_uid}" -e "SNAPSHOT_GID=${host_gid}" \
    -v "$rollback:/snapshot" app -eu -c \
    'cp -a /var/lib/homologacion/runtime/. /snapshot/; chown -R "${SNAPSHOT_UID}:${SNAPSHOT_GID}" /snapshot'
pre_restore_dir="${BACKUP_DIR:-${compose_dir}/backups}/pre-restore"
mkdir -p "$pre_restore_dir"
BACKUP_DIR="$pre_restore_dir" RUNTIME_SOURCE_DIR="$rollback" \
    sh "$script_dir/backup-runtime.sh" >/dev/null
pre_restore="$(find "$pre_restore_dir" -type f \
    \( -name 'homologacion-app-runtime-*.tar.gz' -o -name 'homologacion-app-runtime-*.tar.gz.enc' \) \
    -print | sort | tail -n 1)"
[ -n "$pre_restore" ] || { echo "No se creó respaldo previo." >&2; exit 70; }

replaced=1
replace_volume_from "$staging"
compose run --rm --no-deps --entrypoint python app \
    deployment/onprem/persistence_probe.py >/dev/null
restart_services
replaced=0
services_stopped=0
trap - EXIT HUP INT TERM
find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
rm -rf "$work_dir"
echo "Restore app_runtime verificado. Rollback preservado: ${pre_restore}"
