#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
backup_dir="${BACKUP_DIR:-${compose_dir}/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"
rpo_hours="${BACKUP_RPO_HOURS:-24}"
rto_hours="${BACKUP_RTO_HOURS:-8}"
docker_bin="${DOCKER_BIN:-docker}"
encrypted=false

case "$backup_dir" in ''|/) echo "BACKUP_DIR inseguro." >&2; exit 78;; esac
case "$retention_days" in ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS inválido." >&2; exit 78;; esac
[ "$retention_days" -ge 1 ] && [ "$retention_days" -le 3650 ] || {
    echo "BACKUP_RETENTION_DAYS fuera de rango." >&2; exit 78;
}
case "$rpo_hours:$rto_hours" in *[!0-9:]*) echo "RPO/RTO inválido." >&2; exit 78;; esac
if [ "$mode" = production ] && [ "$encryption_required" != true ]; then
    echo "Producción exige cifrado de respaldos." >&2
    exit 78
fi
if [ "$encryption_required" = true ] || [ -n "$encryption_key_file" ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    command -v openssl >/dev/null 2>&1 || {
        echo "OpenSSL es obligatorio para cifrar respaldos." >&2; exit 69;
    }
    encrypted=true
fi

suffix=.dump
[ "$encrypted" = false ] || suffix=.dump.enc
target="${backup_dir}/homologacion-${timestamp}-$$${suffix}"
partial="${target}.partial"
fifo="${target}.fifo"
completed=0

cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    rm -f "$fifo"
    if [ "$code" -ne 0 ] && [ "$completed" -eq 0 ]; then
        rm -f "$partial" "$target" "${target}.sha256" \
            "${target}.meta.json" "${target}.meta.json.sha256"
    fi
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

umask 077
mkdir -p "${backup_dir}"

cd "${compose_dir}"
compose() { "$docker_bin" compose "$@"; }
if [ "$encrypted" = true ]; then
    mkfifo "$fifo"
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:${encryption_key_file}" < "$fifo" > "$partial" &
    encrypt_pid=$!
    set +e
    compose exec -T db sh -eu -c \
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
        > "$fifo"
    dump_status=$?
    wait "$encrypt_pid"
    encrypt_status=$?
    set -e
    rm -f "$fifo"
    [ "$dump_status" -eq 0 ] && [ "$encrypt_status" -eq 0 ] || exit 70
else
    compose exec -T db sh -eu -c \
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
        > "${partial}"
fi

test -s "${partial}"
mv "${partial}" "${target}"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${target}" > "${target}.sha256"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${target}" > "${target}.sha256"
else
    echo "No se encontro sha256sum ni shasum; respaldo invalidado." >&2
    rm -f "${target}" "${target}.sha256"
    exit 69
fi
cat > "${target}.meta.json" <<EOF
{"created_at":"${timestamp}","encrypted":${encrypted},"rpo_hours":${rpo_hours},"rto_hours":${rto_hours},"retention_days":${retention_days},"format":"postgres-custom"}
EOF
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${target}.meta.json" > "${target}.meta.json.sha256"
else
    shasum -a 256 "${target}.meta.json" > "${target}.meta.json.sha256"
fi
find "$backup_dir" -type f \
    \( -name '*.dump' -o -name '*.dump.enc' -o -name '*.sha256' -o -name '*.meta.json' \) \
    -mtime "+${retention_days}" -delete
completed=1
trap - EXIT HUP INT TERM
echo "Respaldo creado: ${target}"
