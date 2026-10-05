#!/bin/sh
set -eu

runtime_source_env="${RUNTIME_SOURCE_DIR:-}"
runtime_source="$runtime_source_env"
source_confirmed_quiesced=false
case "$#:${1:-}:${3:-}" in
    0::) ;;
    3:--source-dir:--confirm-quiesced)
        [ -z "$runtime_source_env" ] || {
            echo "No combine RUNTIME_SOURCE_DIR con --source-dir." >&2
            exit 64
        }
        runtime_source="$2"
        source_confirmed_quiesced=true
        ;;
    *)
        echo "Uso: $0 [--source-dir RUTA --confirm-quiesced]" >&2
        exit 64
        ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
archive_tool="${compose_dir}/runtime_archive.py"
auth_tool="${compose_dir}/backup_auth.py"
backup_dir="${BACKUP_DIR:-${compose_dir}/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mode="${ONPREM_DEPLOYMENT_MODE:-production}"
encryption_required="${BACKUP_ENCRYPTION_REQUIRED:-true}"
authentication_required="${BACKUP_AUTHENTICATION_REQUIRED:-${encryption_required}}"
encryption_key_file="${BACKUP_ENCRYPTION_KEY_FILE:-}"
backup_key_id="${BACKUP_KEY_ID:-}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"
rpo_hours="${BACKUP_RPO_HOURS:-24}"
rto_hours="${BACKUP_RTO_HOURS:-8}"
docker_bin="${DOCKER_BIN:-docker}"
encrypted=false
authenticated=false
host_uid="$(id -u)"
host_gid="$(id -g)"

case "$backup_dir" in ''|/) echo "BACKUP_DIR inseguro." >&2; exit 78;; esac
case "$timestamp" in ????????T??????Z) ;; *) echo "Timestamp de backup inválido." >&2; exit 78;; esac
case "$timestamp" in *[!0-9TZ]*) echo "Timestamp de backup inválido." >&2; exit 78;; esac
case "$mode" in production|evaluation) ;; *) echo "ONPREM_DEPLOYMENT_MODE inválido." >&2; exit 78;; esac
if [ "$mode" = production ] && [ -n "$runtime_source" ] && \
    [ "$source_confirmed_quiesced" != true ]; then
    echo "RUNTIME_SOURCE_DIR sólo está permitido en evaluación." >&2
    exit 78
fi
case "$encryption_required:$authentication_required" in
    true:true|true:false|false:true|false:false) ;;
    *) echo "Configuración de cifrado/autenticación inválida." >&2; exit 78;;
esac
if [ -n "$backup_key_id" ]; then
    case "$backup_key_id" in
        [A-Za-z0-9]*) ;;
        *) echo "BACKUP_KEY_ID inválido." >&2; exit 78;;
    esac
    case "$backup_key_id" in *[!A-Za-z0-9._-]*) echo "BACKUP_KEY_ID inválido." >&2; exit 78;; esac
    [ "${#backup_key_id}" -le 64 ] || { echo "BACKUP_KEY_ID inválido." >&2; exit 78; }
fi
case "$host_uid:$host_gid" in *[!0-9:]*) echo "UID/GID del operador inválido." >&2; exit 78;; esac
case "$retention_days" in ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS inválido." >&2; exit 78;; esac
case "$retention_days" in 0|[1-9]*) ;; *) echo "BACKUP_RETENTION_DAYS inválido." >&2; exit 78;; esac
[ "$retention_days" -ge 1 ] && [ "$retention_days" -le 3650 ] || {
    echo "BACKUP_RETENTION_DAYS fuera de rango." >&2; exit 78;
}
case "$rpo_hours" in ''|*[!0-9]*) echo "BACKUP_RPO_HOURS inválido." >&2; exit 78;; esac
case "$rto_hours" in ''|*[!0-9]*) echo "BACKUP_RTO_HOURS inválido." >&2; exit 78;; esac
case "$rpo_hours" in 0|[1-9]*) ;; *) echo "BACKUP_RPO_HOURS inválido." >&2; exit 78;; esac
case "$rto_hours" in 0|[1-9]*) ;; *) echo "BACKUP_RTO_HOURS inválido." >&2; exit 78;; esac
if [ "$mode" = production ] && [ "$encryption_required" != true ]; then
    echo "Producción exige cifrado de app_runtime." >&2; exit 78
fi
if [ "$mode" = production ] && [ "$authentication_required" != true ]; then
    echo "Producción exige autenticación de app_runtime." >&2; exit 78
fi
if [ "$encryption_required" = true ] || [ -n "$encryption_key_file" ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    command -v openssl >/dev/null 2>&1 || exit 69
    encrypted=true
fi
if [ "$encrypted" = true ] || [ "$authentication_required" = true ]; then
    [ -s "$encryption_key_file" ] || {
        echo "No se puede leer BACKUP_ENCRYPTION_KEY_FILE." >&2; exit 78;
    }
    [ -f "$auth_tool" ] || { echo "No se encontró el autenticador de respaldos." >&2; exit 69; }
    authenticated=true
fi

prepare_backup_dir() {
    python3 - "$backup_dir" <<'PY'
import os
import stat
import sys


def reject(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(78)


path = os.path.abspath(sys.argv[1])
try:
    if not os.path.lexists(path):
        try:
            os.makedirs(path, mode=0o700)
        except FileExistsError:
            pass
    info = os.lstat(path)
except OSError:
    reject("No se puede preparar BACKUP_DIR.")
if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
    reject("BACKUP_DIR debe ser un directorio real, no un enlace simbólico.")
if info.st_uid != os.geteuid():
    reject("BACKUP_DIR debe pertenecer al operador del backup.")
if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
    reject("BACKUP_DIR no puede permitir escritura a grupo u otros.")
flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
try:
    descriptor = os.open(path, flags)
    opened = os.fstat(descriptor)
except OSError:
    reject("No se puede abrir BACKUP_DIR de forma segura.")
finally:
    try:
        os.close(descriptor)
    except (NameError, OSError):
        pass
if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
    reject("BACKUP_DIR cambió durante su validación.")
print(path)
PY
}

publish_bundle() {
    python3 - "$backup_dir" "$stage_dir" "$bundle_name" "$authenticated" <<'PY'
import os
import stat
import sys


def fail(message: str, code: int = 73) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


destination, staging, primary, authenticated = sys.argv[1:]
names = [
    f"{primary}.sha256",
    f"{primary}.meta.json",
    f"{primary}.meta.json.sha256",
]
if authenticated == "true":
    names.append(f"{primary}.auth.json")
# El artefacto principal se hace visible al final, cuando todos sus sidecars existen.
names.append(primary)

try:
    destination_info = os.lstat(destination)
    staging_info = os.lstat(staging)
except OSError:
    fail("No se puede validar el staging del backup.")
if stat.S_ISLNK(destination_info.st_mode) or not stat.S_ISDIR(destination_info.st_mode):
    fail("BACKUP_DIR dejó de ser un directorio seguro.", 78)
if destination_info.st_uid != os.geteuid() or destination_info.st_mode & 0o022:
    fail("BACKUP_DIR dejó de cumplir propietario o permisos seguros.", 78)
if stat.S_ISLNK(staging_info.st_mode) or not stat.S_ISDIR(staging_info.st_mode):
    fail("El staging del backup no es un directorio real.")
if staging_info.st_uid != os.geteuid() or staging_info.st_mode & 0o077:
    fail("El staging del backup no es privado.")

source_info: dict[str, os.stat_result] = {}
source_descriptors: list[int] = []
try:
    for name in names:
        source = os.path.join(staging, name)
        info = os.lstat(source)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            fail("El bundle contiene un artefacto que no es archivo regular.")
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            fail("Los artefactos del backup deben pertenecer al operador y usar modo 0600.")
        descriptor = os.open(
            source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
        source_descriptors.append(descriptor)
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            fail("Un artefacto del staging cambió durante su validación.")
        os.fsync(descriptor)
        source_info[name] = info

    directory_fd = os.open(
        destination,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    opened_destination = os.fstat(directory_fd)
    if (opened_destination.st_dev, opened_destination.st_ino) != (
        destination_info.st_dev,
        destination_info.st_ino,
    ):
        fail("BACKUP_DIR cambió antes de publicar el bundle.", 78)

    for name in names:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        fail(f"Colisión: ya existe un artefacto del backup: {name}")

    created: list[str] = []
    try:
        for name in names:
            os.link(
                os.path.join(staging, name),
                name,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
            created.append(name)
        os.fsync(directory_fd)
    except Exception:
        for name in reversed(created):
            try:
                published = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                expected = source_info[name]
                if (published.st_dev, published.st_ino) == (
                    expected.st_dev,
                    expected.st_ino,
                ):
                    os.unlink(name, dir_fd=directory_fd)
            except OSError:
                pass
        try:
            os.fsync(directory_fd)
        except OSError:
            pass
        raise
finally:
    for descriptor in source_descriptors:
        try:
            os.close(descriptor)
        except OSError:
            pass
    try:
        os.close(directory_fd)
    except (NameError, OSError):
        pass
PY
}

umask 077
backup_dir="$(prepare_backup_dir)"
stage_dir="$(mktemp -d "${backup_dir}/.homologacion-runtime-stage.XXXXXX")"
chmod 0700 "$stage_dir"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/homologacion-runtime-backup.XXXXXX")"
work_dir="$(CDPATH= cd -- "$work_dir" && pwd -P)"
snapshot="${work_dir}/runtime"
plain="${work_dir}/app-runtime.tar.gz"
captured_key="${work_dir}/backup.key"
app_was_running=0
proxy_was_running=0
services_stopped=0

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
    [ -z "${stage_dir:-}" ] || rm -rf "$stage_dir"
    exit "$code"
}
trap cleanup EXIT HUP INT TERM

if [ "$authenticated" = true ]; then
    python3 "$auth_tool" capture-key --key-file "$encryption_key_file" \
        --output "$captured_key"
    encryption_key_file="$captured_key"
fi

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
bundle_name="homologacion-app-runtime-${timestamp}-$$${suffix}"
stage_target="${stage_dir}/${bundle_name}"
target="${backup_dir}/${bundle_name}"
if [ "$encrypted" = true ]; then
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -md sha256 \
        -pass "file:${encryption_key_file}" -in "$plain" -out "$stage_target"
else
    mv "$plain" "$stage_target"
fi

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1"
    else echo "No se encontró SHA-256." >&2; exit 69
    fi
}
artifact_digest="$(sha256_file "$stage_target" | awk '{print $1}')"
printf '%s  %s\n' "$artifact_digest" "$bundle_name" > "$stage_target.sha256"
authentication=none
[ "$authenticated" = false ] || authentication=hmac-sha256
cat > "$stage_target.meta.json" <<EOF
{"authentication":"${authentication}","created_at":"${timestamp}","encrypted":${encrypted},"envelope_version":2,"format":"homologacion-app-runtime-v1","retention_days":${retention_days},"rpo_hours":${rpo_hours},"rto_hours":${rto_hours}}
EOF
metadata_digest="$(sha256_file "$stage_target.meta.json" | awk '{print $1}')"
printf '%s  %s.meta.json\n' "$metadata_digest" "$bundle_name" \
    > "$stage_target.meta.json.sha256"
if [ "$authenticated" = true ]; then
    if [ -n "$backup_key_id" ]; then
        python3 "$auth_tool" sign --artifact "$stage_target" \
            --metadata "$stage_target.meta.json" --key-file "$encryption_key_file" \
            --output "$stage_target.auth.json" --payload-kind app-runtime \
            --key-id "$backup_key_id"
    else
        python3 "$auth_tool" sign --artifact "$stage_target" \
            --metadata "$stage_target.meta.json" --key-file "$encryption_key_file" \
            --output "$stage_target.auth.json" --payload-kind app-runtime
    fi
fi
chmod 0600 "$stage_target" "$stage_target.sha256" \
    "$stage_target.meta.json" "$stage_target.meta.json.sha256"
[ "$authenticated" = false ] || chmod 0600 "$stage_target.auth.json"
publish_bundle
python3 - "$backup_dir" "$retention_days" <<'PY'
import os
import re
import stat
import sys
import time


backup_dir, retention_days_text = sys.argv[1:]
retention_days = int(retention_days_text)
bundle_member = re.compile(
    r"homologacion-app-runtime-\d{8}T\d{6}Z-\d+\.tar\.gz(?:\.enc)?"
    r"(?:\.sha256|\.meta\.json(?:\.sha256)?|\.auth\.json)?\Z"
)
directory_fd = os.open(
    backup_dir,
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
)
try:
    now = time.time()
    with os.scandir(backup_dir) as entries:
        for entry in entries:
            if bundle_member.fullmatch(entry.name) is None:
                continue
            info = entry.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                continue
            age_days = int(max(0.0, now - info.st_mtime) // 86400)
            if age_days > retention_days:
                os.unlink(entry.name, dir_fd=directory_fd)
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
restart_services
services_stopped=0
trap - EXIT HUP INT TERM
find "$work_dir" -type f -exec sh -c 'for item do : > "$item"; done' sh {} + 2>/dev/null || true
rm -rf "$work_dir"
rm -rf "$stage_dir"
echo "Respaldo app_runtime creado: ${target}"
