#!/usr/bin/env bash
# ============================================================
# TaskingAI Development Environment Setup
# ============================================================
# Set up local development environment with all shared packages.
#
# Usage:
#   ./scripts/setup-dev.sh            # Setup all shared packages
#   ./scripts/setup-dev.sh python       # Install Python shared packages
#   ./scripts/setup-dev.sh npm          # Install NPM shared packages
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

setup_python() {
    echo "============================================================"
    echo "Setting up Python shared packages"
    echo "============================================================"

    if ! command -v pip &> /dev/null; then
        echo "ERROR: pip is not installed"
        exit 1
    fi

    echo ""
    echo "Installing taskingai-contracts (editable mode)..."
    pip install -e "$PROJECT_ROOT/contracts/python"

    echo ""
    echo "Installing taskingai-common (tkhelper, editable mode)..."
    pip install -e "$PROJECT_ROOT/common/python"

    echo ""
    echo "✓ Python shared packages installed"
    echo ""
}

setup_npm() {
    echo "============================================================"
    echo "Setting up NPM shared packages"
    echo "============================================================"

    if ! command -v npm &> /dev/null; then
        echo "ERROR: npm is not installed"
        exit 1
    fi

    echo ""
    echo "Building @taskingai/contracts package..."
    cd "$PROJECT_ROOT/contracts/npm"
    npm install
    npm run build 2>/dev/null || echo "Note: TypeScript build skipped (types only used at build time)"

    echo ""
    echo "✓ NPM shared packages ready"
    echo ""
}

case "${1:-all}" in
    python)
        setup_python
        ;;
    npm)
        setup_npm
        ;;
    all)
        setup_python
        setup_npm
        ;;
    *)
        echo "Usage: $0 {python|npm|all}"
        exit 1
        ;;
esac

echo "============================================================"
echo "Development environment setup complete!"
echo "============================================================"
echo ""
echo "Python packages:"
echo "  - taskingai-contracts (from contracts/python)"
echo "  - taskingai-common (tkhelper, from common/python)"
echo ""
echo "NPM packages:"
echo "  - @taskingai/contracts (from contracts/npm)"
echo ""
echo "To use in Python services, import directly:"
echo "  from taskingai_contracts import validate_artifact"
echo "  from tkhelper import ErrorCode, raise_http_error"
echo ""
echo "To use in frontend, import from @taskingai/contracts"
echo "============================================================"
