#!/usr/bin/env bash
# Rollback: AccountTypeFilter (Sprint 28.4)
# Uso: bash reports/rollback_account_type_filter.sh

set -euo pipefail

echo "=== Rollback: AccountTypeFilter (Sprint 28.4) ==="

# Restore pipeline files
git checkout -- pipeline/features.py pipeline/homologation_pipeline.py
echo "✓ pipeline/features.py restored"
echo "✓ pipeline/homologation_pipeline.py restored"

# Remove new files
rm -f tests/test_account_type_filter.py
rm -f reports/account_type_filter.md
rm -f reports/account_type_filter.json
rm -f reports/run_account_type_filter.py
rm -f reports/account_type_validation_filter.json
rm -f reports/account_type_filter_checkpoint.json
rm -f reports/rollback_account_type_filter.sh
echo "✓ New files removed"

echo ""
echo "Verify:"
echo "  git diff --stat pipeline/  # must be empty"
echo "  python3 -m pytest tests/test_account_type_filter.py -q  # file not found"
echo "  python3 -m pytest tests/ -q  # 905 passed, 14 failed"
echo ""
echo "=== Rollback complete ==="
