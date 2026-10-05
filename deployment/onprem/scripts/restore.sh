#!/bin/sh
set -eu

legacy_flag=false
case "$#:${2:-}:${3:-}" in
    2:--confirm:) ;;
    3:--confirm:--allow-legacy-unauthenticated) legacy_flag=true ;;
    *)
        echo "Uso: $0 RUTA_RESPALDO.dump[.enc] --confirm [--allow-legacy-unauthenticated]" >&2
        exit 64
        ;;
esac

source_file="$1"
checksum_file="${source_file}.sha256"
metadata_file="${source_file}.meta.json"
auth_file="${source_file}.auth.json"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
authentication_required="${BACKUP_AUTHENTICATION_REQUIRED:-${encryption_required}}"
allow_legacy="${BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE:-false}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
docker_bin="${DOCKER_BIN:-docker}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
auth_tool="${compose_dir}/backup_auth.py"
if [ ! -s "$source_file" ] || [ ! -s "$checksum_file" ]; then
    echo "Se requiere un respaldo no vacío y su archivo .sha256." >&2
    exit 66
fi
case "$mode" in production|evaluation) ;; *) echo "ONPREM_DEPLOYMENT_MODE inválido." >&2; exit 78;; esac
case "$encryption_required:$authentication_required" in
    true:true|true:false|false:true|false:false) ;;
    *) echo "Configuración de cifrado/autenticación inválida." >&2; exit 78;;
esac
case "$source_file" in *.enc) encrypted=true;; *) encrypted=false;; esac
if [ "$mode" = production ] && [ "$encryption_required" != true ]; then
    echo "Producción exige restore de respaldos cifrados." >&2
    exit 78
fi
if [ "$mode" = production ] && [ "$authentication_required" != true ]; then
    echo "Producción exige autenticación de respaldos." >&2
    exit 78
fi
if [ "$encryption_required" = true ] && [ "$encrypted" != true ]; then
    echo "La configuración rechaza respaldos sin cifrar." >&2
    exit 78
fi

umask 077
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/homologacion-postgres-restore.XXXXXX")"
work_dir="$(CDPATH= cd -- "$work_dir" && pwd -P)"
temp_root="$(dirname -- "$work_dir")"
stable_source="${work_dir}/authenticated.payload"
stable_metadata="${work_dir}/authenticated.meta.json"
stable_key="${work_dir}/authenticated.key"
stable_checksum="${work_dir}/payload.sha256"
stable_metadata_checksum="${work_dir}/metadata.sha256"
source_for_restore="$source_file"
metadata_for_restore="$metadata_file"
key_for_restore="$encryption_key_file"
checksum_for_restore="$checksum_file"
metadata_checksum_for_restore="${metadata_file}.sha256"
cleanup_early() {
    code=$?
    trap - EXIT HUP INT TERM
    find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
    rm -rf "$work_dir"
    exit "$code"
}
trap cleanup_early EXIT HUP INT TERM

authenticated=false
if [ -e "$auth_file" ] || [ -L "$auth_file" ]; then
    authenticated=true
    [ -s "$metadata_file" ] || { echo "Autenticación del respaldo inválida." >&2; exit 65; }
    [ -f "$auth_tool" ] || { echo "Autenticación del respaldo inválida." >&2; exit 65; }
    python3 "$auth_tool" verify --artifact "$source_file" \
        --metadata "$metadata_file" --key-file "$encryption_key_file" \
        --auth "$auth_file" --payload-kind postgres-custom \
        --staged-artifact "$stable_source" \
        --staged-metadata "$stable_metadata" \
        --staged-key "$stable_key" || exit $?
    source_for_restore="$stable_source"
    metadata_for_restore="$stable_metadata"
    key_for_restore="$stable_key"
else
    if [ "$mode" = production ] || [ "$allow_legacy" != true ] || [ "$legacy_flag" != true ]; then
        echo "Autenticación del respaldo inválida." >&2
        exit 65
    fi
    cp "$source_file" "$stable_source"
    chmod 600 "$stable_source"
    source_for_restore="$stable_source"
fi

cp "$checksum_file" "$stable_checksum"
chmod 600 "$stable_checksum"
checksum_for_restore="$stable_checksum"
if [ "$authenticated" = true ] || [ "$mode" = production ]; then
    [ -s "$metadata_file.sha256" ] || {
        echo "Falta checksum de metadatos de respaldo." >&2; exit 66;
    }
    cp "$metadata_file.sha256" "$stable_metadata_checksum"
    chmod 600 "$stable_metadata_checksum"
    metadata_checksum_for_restore="$stable_metadata_checksum"
fi

if [ "$authenticated" = true ]; then
    python3 - "$metadata_for_restore" "$encrypted" <<'PY' || {
import json
import sys

def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result

try:
    with open(sys.argv[1], "r", encoding="utf-8") as stream:
        metadata = json.load(stream, object_pairs_hook=no_duplicates)
    expected_encrypted = sys.argv[2] == "true"
    valid = (
        isinstance(metadata, dict)
        and metadata.get("format") == "postgres-custom"
        and type(metadata.get("envelope_version")) is int
        and metadata.get("envelope_version") == 2
        and metadata.get("authentication") == "hmac-sha256"
        and metadata.get("encrypted") is expected_encrypted
    )
except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
    valid = False
raise SystemExit(0 if valid else 65)
PY
        echo "Metadatos autenticados inválidos." >&2
        exit 65
    }
fi

if [ "$encrypted" = true ]; then
    if [ "$authenticated" != true ]; then
        [ -s "$encryption_key_file" ] || {
            echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
        }
        cp "$encryption_key_file" "$stable_key"
        chmod 600 "$stable_key"
        key_for_restore="$stable_key"
    fi
    [ -s "$key_for_restore" ] || {
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

if [ "$authenticated" = true ] || [ "$mode" = production ]; then
    [ -s "$metadata_checksum_for_restore" ] || {
        echo "Falta checksum de metadatos de respaldo." >&2; exit 66;
    }
    expected_metadata="$(awk 'NR == 1 {print $1}' "$metadata_checksum_for_restore")"
    actual_metadata="$(sha256_file "$metadata_for_restore")"
    [ "${#expected_metadata}" -eq 64 ] && \
        [ "$(printf '%s' "$expected_metadata" | tr 'A-F' 'a-f')" = "$actual_metadata" ] || {
        echo "Checksum de metadatos no coincide." >&2; exit 65;
    }
fi

expected="$(awk 'NR == 1 {print $1}' "$checksum_for_restore")"
actual="$(sha256_file "$source_for_restore")"
case "$expected" in *[!0-9a-fA-F]*|'') echo "Checksum inválido." >&2; exit 65;; esac
[ "${#expected}" -eq 64 ] || { echo "Checksum inválido." >&2; exit 65; }
[ "$(printf '%s' "$expected" | tr 'A-F' 'a-f')" = "$actual" ] || {
    echo "Checksum no coincide; no se modificó la base." >&2
    exit 65
}
database="${POSTGRES_DB:-homologacion}"
case "$database" in ''|*[!A-Za-z0-9_]*) echo "POSTGRES_DB inválido." >&2; exit 78;; esac
[ "${#database}" -le 30 ] || { echo "POSTGRES_DB demasiado largo para restore seguro." >&2; exit 78; }
suffix="$(date -u +%Y%m%dT%H%M%SZ)_$$"
staging="${database}_restore_${suffix}"
previous="${database}_before_${suffix}"
pre_restore_dir="${BACKUP_DIR:-${compose_dir}/backups}/pre-restore"
pre_restore_dir="$(python3 - "$pre_restore_dir" <<'PY'
import os
import sys

print(os.path.abspath(sys.argv[1]))
PY
)"
services_stopped=0
swapped=0
app_was_running=0
proxy_was_running=0
restore_input="$source_for_restore"
decrypted_file=""

compose() { "$docker_bin" compose "$@"; }
if [ "$encrypted" = true ]; then
    decrypted_file="${work_dir}/restore.dump"
    : > "$decrypted_file"
    chmod 600 "$decrypted_file"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
        -pass "file:${key_for_restore}" -in "$source_for_restore" -out "$decrypted_file"
    restore_input="$decrypted_file"
fi

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
    find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
    rm -rf "$work_dir"
    restart_services || { [ "$code" -ne 0 ] || code=70; }
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

cd "${compose_dir}"
running_services="$(compose ps --services --filter status=running)"
printf '%s\n' "$running_services" | grep -qx app && app_was_running=1 || true
printf '%s\n' "$running_services" | grep -qx reverse-proxy && proxy_was_running=1 || true
compose stop app reverse-proxy >/dev/null
services_stopped=1
TMPDIR="$temp_root" BACKUP_DIR="$pre_restore_dir" "$script_dir/backup.sh" >/dev/null

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
find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
rm -rf "$work_dir"

echo "Restauración verificada. Base anterior preservada como: ${previous}"
