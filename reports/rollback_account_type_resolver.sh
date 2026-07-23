#!/usr/bin/env bash
# Rollback: AccountTypeResolver (Sprint 28.3)
# Uso: bash reports/rollback_account_type_resolver.sh

set -euo pipefail

echo "=== Rollback: AccountTypeResolver (Sprint 28.3) ==="

# Restore parser_universal.py (reverts both Sprint 28.2 and 28.3)
git checkout -- parser_universal.py
echo "✓ parser_universal.py restored"

# Remove new files
rm -f parsers/account_type_resolver.py
rm -f tests/test_account_type_resolver.py
echo "✓ New files removed"

# Remove reports
rm -f reports/account_type_resolver.md
rm -f reports/account_type_resolver.json
rm -f reports/account_type_validation.json
rm -f reports/account_type_validation_checkpoint.json
rm -f reports/run_account_type_validation.py
echo "✓ Reports removed"

echo ""
echo "Verify:"
echo "  git diff --stat parser_universal.py  # must be empty"
echo "  python3 -m pytest tests/ -q          # 869 passed, 14 failed"
echo ""
echo "=== Rollback complete ==="
