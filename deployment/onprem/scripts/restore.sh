#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--confirm" ]; then
    echo "Uso: $0 RUTA_RESPALDO.dump --confirm" >&2
    exit 64
fi

source_file="$1"
checksum_file="${source_file}.sha256"
metadata_file="${source_file}.meta.json"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
docker_bin="${DOCKER_BIN:-docker}"
if [ ! -s "$source_file" ] || [ ! -s "$checksum_file" ]; then
    echo "Se requiere un respaldo no vacío y su archivo .sha256." >&2
    exit 66
fi
if [ "$mode" = production ] && [ "$encryption_required" != true ]; then
    echo "Producción exige restore de respaldos cifrados." >&2
    exit 78
fi
if [ "$mode" = production ]; then
    [ -s "$metadata_file" ] && grep -q '"encrypted":true' "$metadata_file" || {
        echo "Producción exige metadatos válidos de respaldo cifrado." >&2
        exit 78
    }
fi
case "$source_file" in *.enc) encrypted=true;; *) encrypted=false;; esac
if [ "$encryption_required" = true ] && [ "$encrypted" != true ]; then
    echo "Producción rechaza respaldos sin cifrar." >&2
    exit 78
fi
if [ "$encrypted" = true ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    command -v openssl >/dev/null 2>&1 || exit 69
fi

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
    else echo "No se encontró una herramienta SHA-256." >&2; exit 69
    fi
}

if [ "$mode" = production ]; then
    metadata_checksum_file="${metadata_file}.sha256"
    [ -s "$metadata_checksum_file" ] || {
        echo "Falta checksum de metadatos de respaldo." >&2; exit 66;
    }
    expected_metadata="$(awk 'NR == 1 {print $1}' "$metadata_checksum_file")"
    actual_metadata="$(sha256_file "$metadata_file")"
    [ "${#expected_metadata}" -eq 64 ] && \
        [ "$(printf '%s' "$expected_metadata" | tr 'A-F' 'a-f')" = "$actual_metadata" ] || {
        echo "Checksum de metadatos no coincide." >&2; exit 65;
    }
fi

expected="$(awk 'NR == 1 {print $1}' "$checksum_file")"
actual="$(sha256_file "$source_file")"
case "$expected" in *[!0-9a-fA-F]*|'') echo "Checksum inválido." >&2; exit 65;; esac
[ "${#expected}" -eq 64 ] || { echo "Checksum inválido." >&2; exit 65; }
[ "$(printf '%s' "$expected" | tr 'A-F' 'a-f')" = "$actual" ] || {
    echo "Checksum no coincide; no se modificó la base." >&2
    exit 65
}
source_dir="$(CDPATH= cd -- "$(dirname -- "${source_file}")" && pwd)"
source_file="${source_dir}/$(basename -- "${source_file}")"

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
database="${POSTGRES_DB:-homologacion}"
case "$database" in ''|*[!A-Za-z0-9_]*) echo "POSTGRES_DB inválido." >&2; exit 78;; esac
[ "${#database}" -le 30 ] || { echo "POSTGRES_DB demasiado largo para restore seguro." >&2; exit 78; }
suffix="$(date -u +%Y%m%dT%H%M%SZ)_$$"
staging="${database}_restore_${suffix}"
previous="${database}_before_${suffix}"
pre_restore_dir="${BACKUP_DIR:-${compose_dir}/backups}/pre-restore"
services_stopped=0
swapped=0
app_was_running=0
proxy_was_running=0
restore_input="$source_file"
decrypted_file=""

compose() { "$docker_bin" compose "$@"; }
early_cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    [ -z "$decrypted_file" ] || rm -f "$decrypted_file"
    exit "$code"
}
trap early_cleanup EXIT HUP INT TERM
if [ "$encrypted" = true ]; then
    decrypted_file="$(mktemp "${TMPDIR:-/tmp}/homologacion-restore.XXXXXX.dump")"
    chmod 600 "$decrypted_file"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
        -pass "file:${encryption_key_file}" -in "$source_file" -out "$decrypted_file"
    restore_input="$decrypted_file"
fi

restart_services() {
    if [ "$services_stopped" -eq 1 ]; then
        [ "$app_was_running" -eq 0 ] || compose start app >/dev/null 2>&1 || true
        [ "$proxy_was_running" -eq 0 ] || compose start reverse-proxy >/dev/null 2>&1 || true
    fi
}

cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$code" -ne 0 ] && [ "$swapped" -eq 0 ]; then
        compose exec -T db sh -eu -c '
            psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
              -v current="$1" -v previous="$2" <<SQL
ALTER DATABASE :"previous" RENAME TO :"current";
SQL
        ' sh "$database" "$previous" >/dev/null 2>&1 || true
        compose exec -T db sh -eu -c \
            'dropdb -U "$POSTGRES_USER" --if-exists "$1"' sh "$staging" \
            >/dev/null 2>&1 || true
    fi
    [ -z "$decrypted_file" ] || rm -f "$decrypted_file"
    restart_services
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

cd "${compose_dir}"
running_services="$(compose ps --services --filter status=running)"
printf '%s\n' "$running_services" | grep -qx app && app_was_running=1 || true
printf '%s\n' "$running_services" | grep -qx reverse-proxy && proxy_was_running=1 || true
compose stop app reverse-proxy >/dev/null
services_stopped=1
BACKUP_DIR="$pre_restore_dir" "$script_dir/backup.sh" >/dev/null

compose exec -T db sh -eu -c \
    'createdb -U "$POSTGRES_USER" "$1"' sh "$staging"
compose exec -T db sh -eu -c \
    'pg_restore -U "$POSTGRES_USER" -d "$1" --no-owner --exit-on-error' sh "$staging" \
    < "${restore_input}"
compose exec -T db sh -eu -c \
    'psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -c "SELECT 1" >/dev/null' \
    sh "$staging"

compose exec -T db sh -eu -c '
    psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
      -v current="$1" -v previous="$2" -v staging="$3" <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
 WHERE datname = :'current' AND pid <> pg_backend_pid();
ALTER DATABASE :"current" RENAME TO :"previous";
ALTER DATABASE :"staging" RENAME TO :"current";
SQL
' sh "$database" "$previous" "$staging"
swapped=1
restart_services
services_stopped=0
trap - EXIT HUP INT TERM
[ -z "$decrypted_file" ] || rm -f "$decrypted_file"

echo "Restauración verificada. Base anterior preservada como: ${previous}"
