#!/bin/sh
# Shared by runtime maintenance commands. Preserve the caller's deployment.
compose() {
    if [ -n "${ONPREM_COMPOSE_OVERRIDE:-}" ]; then
        set -- -f "$compose_dir/docker-compose.yml" -f "$ONPREM_COMPOSE_OVERRIDE" "$@"
    else
        set -- -f "$compose_dir/docker-compose.yml" "$@"
    fi
    if [ -n "${ONPREM_COMPOSE_ENV_FILE:-}" ]; then
        set -- --env-file "$ONPREM_COMPOSE_ENV_FILE" "$@"
    fi
    "${docker_bin:-docker}" compose --project-directory "$compose_dir" "$@"
}
