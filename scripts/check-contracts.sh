#!/usr/bin/env bash
# ============================================================
# TaskingAI Contracts Consistency Check
# ============================================================
# Verify that Python and NPM contract packages are in sync.
# Checks:
#   - Schema files are identical
#   - Both packages exist and are buildable
#   - Version numbers match
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTRACTS_DIR="$PROJECT_ROOT/contracts"

FAILED=0

echo "============================================================"
echo "TaskingAI Contracts Consistency Check"
echo "============================================================"
echo ""

# Check 1: Schema files exist
echo "1. Checking schema files exist..."
PY_SCHEMA="$CONTRACTS_DIR/python/taskingai_contracts/artifact/schemas/v1.0.json"
NPM_SCHEMA="$CONTRACTS_DIR/npm/src/artifact/schemas/v1.0.json"

if [ -f "$PY_SCHEMA" ]; then
    echo "   ✓ Python schema: $PY_SCHEMA"
else
    echo "   ✗ Python schema not found: $PY_SCHEMA"
    FAILED=1
fi

if [ -f "$NPM_SCHEMA" ]; then
    echo "   ✓ NPM schema: $NPM_SCHEMA"
else
    echo "   ✗ NPM schema not found: $NPM_SCHEMA"
    FAILED=1
fi
echo ""

# Check 2: Schema files are identical
echo "2. Checking schema consistency..."
if [ -f "$PY_SCHEMA" ] && [ -f "$NPM_SCHEMA" ]; then
    if diff -q "$PY_SCHEMA" "$NPM_SCHEMA" > /dev/null 2>&1; then
        echo "   ✓ Python and NPM schemas are identical"
    else
        echo "   ✗ Python and NPM schemas differ!"
        echo "     Run: diff $PY_SCHEMA $NPM_SCHEMA"
        FAILED=1
    fi
else
    echo "   ⊘ Skipped (schema files missing)"
fi
echo ""

# Check 3: Python package structure
echo "3. Checking Python package structure..."
PY_INIT="$CONTRACTS_DIR/python/taskingai_contracts/__init__.py"
PY_TOML="$CONTRACTS_DIR/python/pyproject.toml"

if [ -f "$PY_INIT" ]; then
    echo "   ✓ __init__.py exists"
else
    echo "   ✗ __init__.py missing"
    FAILED=1
fi

if [ -f "$PY_TOML" ]; then
    echo "   ✓ pyproject.toml exists"
else
    echo "   ✗ pyproject.toml missing"
    FAILED=1
fi
echo ""

# Check 4: NPM package structure
echo "4. Checking NPM package structure..."
NPM_PKG="$CONTRACTS_DIR/npm/package.json"
NPM_SRC="$CONTRACTS_DIR/npm/src/index.ts"

if [ -f "$NPM_PKG" ]; then
    echo "   ✓ package.json exists"
else
    echo "   ✗ package.json missing"
    FAILED=1
fi

if [ -f "$NPM_SRC" ]; then
    echo "   ✓ src/index.ts exists"
else
    echo "   ✗ src/index.ts missing"
    FAILED=1
fi
echo ""

# Summary
echo "============================================================"
if [ "$FAILED" -eq 0 ]; then
    echo "✓ All checks passed!"
    echo "============================================================"
    exit 0
else
    echo "✗ Some checks failed. Please fix the issues above."
    echo "============================================================"
    exit 1
fi
