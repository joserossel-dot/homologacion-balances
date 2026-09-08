#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compose_dir="$(dirname -- "${script_dir}")"
project_root="$(CDPATH= cd -- "${compose_dir}/../.." && pwd)"

echo "Validando sintaxis de scripts"
sh -n \
    "${compose_dir}/run-app.sh" \
    "${compose_dir}/run-bootstrap.sh" \
    "${script_dir}/backup.sh" \
    "${script_dir}/compose-context.sh" \
    "${script_dir}/backup-runtime.sh" \
    "${script_dir}/restore.sh" \
    "${script_dir}/restore-runtime.sh" \
    "${script_dir}/smoke-test.sh" \
    "${script_dir}/verify-package.sh"

echo "Validando utilidades Python on-premise"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
    "${compose_dir}/bootstrap.py" \
    "${compose_dir}/preflight.py" \
    "${compose_dir}/persistence_probe.py" \
    "${compose_dir}/runtime_archive.py" \
    "${project_root}/scripts/reconcile_local_runtime.py"

if ! command -v docker >/dev/null 2>&1; then
    echo "BLOQUEADO: Docker CLI no esta instalado." >&2
    exit 69
fi

echo "Validando contrato Compose sin usar el daemon"
docker compose --project-directory "${compose_dir}" \
    -f "${compose_dir}/docker-compose.yml" \
    -f "${compose_dir}/docker-compose.evaluation.yml" \
    --env-file "${compose_dir}/.env.example" config --quiet

echo "Ejecutando pruebas estáticas on-premise"
cd "${project_root}"
python3 -m pytest -q tests/onprem tests/persistence/test_local_reconciliation.py

if docker info >/dev/null 2>&1; then
    echo "Docker disponible. Puede ejecutar: deployment/onprem/scripts/smoke-test.sh"
else
    echo "VALIDACION ESTATICA APROBADA. Smoke bloqueado: daemon Docker no disponible."
fi
