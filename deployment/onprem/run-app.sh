#!/bin/sh
set -eu

python deployment/onprem/preflight.py
exec streamlit run app_validacion.py \
    --server.port="${PORT:-8501}" \
    --server.address=0.0.0.0
