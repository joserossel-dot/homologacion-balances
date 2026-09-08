#!/bin/sh
set -eu

python deployment/onprem/preflight.py
exec python deployment/onprem/bootstrap.py
