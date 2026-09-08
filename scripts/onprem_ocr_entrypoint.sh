#!/bin/sh
set -eu

python /app/scripts/ocr_preflight.py \
  --require-spa \
  --compare /app/.ocr_runtime.json

exec /usr/local/bin/run-app "$@"
