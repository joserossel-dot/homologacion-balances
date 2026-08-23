#!/bin/sh
# start.sh — arranca el backend FastAPI (interno, puerto 8000) y luego
# Streamlit (público, puerto $PORT) en el mismo contenedor.
#
# Por qué existe este script: app_validacion.py ahora llama a
# http://localhost:8000/api/v1/analisis/procesar en vez de correr el
# pipeline en el mismo proceso (commit "harden V2 pipeline, unified UI
# endpoints"). Sin este script, el Dockerfile solo arrancaba Streamlit y
# cada archivo subido fallaba con "Error de conexión con el backend
# FastAPI" porque no había nada escuchando en el puerto 8000.
#
# Falla rápido y ruidoso si el backend no levanta — preferible a que
# Streamlit arranque "bien" y falle silenciosamente en cada archivo.

set -e

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_HOST="127.0.0.1"
STREAMLIT_PORT="${PORT:-10000}"
TIMEOUT_SEGUNDOS=30

echo "[start.sh] Arrancando backend FastAPI en :${BACKEND_PORT} ..."
python3 -m uvicorn src.api.main:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --log-level info &
BACKEND_PID=$!

# Si el backend muere, no tiene sentido seguir — sin él, la UI no puede
# clasificar nada (ver comentario arriba).
trap 'echo "[start.sh] Deteniendo backend (pid $BACKEND_PID)..."; kill $BACKEND_PID 2>/dev/null' EXIT

echo "[start.sh] Esperando a que el backend responda (máx ${TIMEOUT_SEGUNDOS}s) ..."
i=0
until curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/docs" > /dev/null 2>&1; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[start.sh] ERROR CRÍTICO: el backend FastAPI murió durante el arranque." >&2
        echo "[start.sh] Revisa DATABASE_URL y los logs de arriba — la app no puede continuar sin el backend." >&2
        exit 1
    fi
    i=$((i + 1))
    if [ "$i" -ge "$TIMEOUT_SEGUNDOS" ]; then
        echo "[start.sh] ERROR CRÍTICO: el backend no respondió en ${TIMEOUT_SEGUNDOS}s." >&2
        exit 1
    fi
    sleep 1
done
echo "[start.sh] Backend OK — respondiendo en http://${BACKEND_HOST}:${BACKEND_PORT}"

# API_URL le dice a app_validacion.py dónde encontrar el backend que
# acabamos de levantar (por defecto ya es localhost:8000, esto lo deja
# explícito para no depender del default silencioso).
export API_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

echo "[start.sh] Arrancando Streamlit en :${STREAMLIT_PORT} (proceso principal) ..."
exec streamlit run app_validacion.py \
    --server.port="${STREAMLIT_PORT}" \
    --server.address=0.0.0.0
