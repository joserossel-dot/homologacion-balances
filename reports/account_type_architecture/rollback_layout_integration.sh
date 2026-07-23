#!/usr/bin/env bash
# Rollback: LayoutDetector integration in parser_universal.py
# Uso: bash reports/account_type_architecture/rollback_layout_integration.sh

set -euo pipefail

echo "=== Rollback: LayoutDetector integration ==="

# Restore parser_universal.py from git
git checkout -- parser_universal.py

echo "✓ parser_universal.py restaurado a versión original (commit HEAD)"
echo ""
echo "Verificar: git diff parser_universal.py debe estar vacío"
git diff --stat parser_universal.py
