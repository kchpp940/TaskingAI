#!/usr/bin/env bash
# ============================================================
# TaskingAI Build Consistency Check
# ============================================================
# Verify all build entry points use consistent build context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PASSED=0
FAILED=0

check() {
    local description="$1"
    local condition="$2"
    
    if eval "$condition"; then
        echo "  ✓ $description"
        PASSED=$((PASSED + 1))
    else
        echo "  ✗ $description"
        FAILED=$((FAILED + 1))
    fi
}

echo "============================================================"
echo "TaskingAI Build Consistency Check"
echo "============================================================"
echo ""

# Section 1: Dockerfile build context
echo "1. Dockerfile build context (all use project root)"
echo "------------------------------------------------------------"
check "backend/Dockerfile mentions project root context" \
    "grep -q 'Build context: project root' $PROJECT_ROOT/backend/Dockerfile"
check "inference/Dockerfile mentions project root context" \
    "grep -q 'Build context: project root' $PROJECT_ROOT/inference/Dockerfile"
check "plugin/Dockerfile mentions project root context" \
    "grep -q 'Build context: project root' $PROJECT_ROOT/plugin/Dockerfile"
check "frontend/Dockerfile mentions project root context" \
    "grep -q 'Build context: project root' $PROJECT_ROOT/frontend/Dockerfile"
echo ""

# Section 2: Dockerfile shared packages installation
echo "2. Dockerfile shared packages (contracts + common)"
echo "------------------------------------------------------------"
check "backend/Dockerfile installs contracts + common" \
    "grep -q 'COPY contracts/python' $PROJECT_ROOT/backend/Dockerfile && grep -q 'COPY common/python' $PROJECT_ROOT/backend/Dockerfile"
check "inference/Dockerfile installs contracts + common" \
    "grep -q 'COPY contracts/python' $PROJECT_ROOT/inference/Dockerfile && grep -q 'COPY common/python' $PROJECT_ROOT/inference/Dockerfile"
check "plugin/Dockerfile installs contracts + common" \
    "grep -q 'COPY contracts/python' $PROJECT_ROOT/plugin/Dockerfile && grep -q 'COPY common/python' $PROJECT_ROOT/plugin/Dockerfile"
echo ""

# Section 3: CI workflows
echo "3. CI workflows build context (all use -f <service>/Dockerfile .)"
echo "------------------------------------------------------------"
check "deploy-backend.yml uses root context" \
    "grep -q 'docker build -f backend/Dockerfile' $PROJECT_ROOT/.github/workflows/deploy-backend.yml"
check "deploy-inference.yml uses root context" \
    "grep -q 'docker build -f inference/Dockerfile' $PROJECT_ROOT/.github/workflows/deploy-inference.yml"
check "deploy-plugin.yml uses root context" \
    "grep -q 'docker build -f plugin/Dockerfile' $PROJECT_ROOT/.github/workflows/deploy-plugin.yml"
check "deploy-frontend.yml uses root context" \
    "grep -q 'docker build -f frontend/Dockerfile' $PROJECT_ROOT/.github/workflows/deploy-frontend.yml"
echo ""

# Section 4: CI workflows shared packages
echo "4. CI workflows install shared packages (contracts + common)"
echo "------------------------------------------------------------"
check "deploy-backend.yml installs contracts + common" \
    "grep -q 'pip install -e contracts/python' $PROJECT_ROOT/.github/workflows/deploy-backend.yml && grep -q 'pip install -e common/python' $PROJECT_ROOT/.github/workflows/deploy-backend.yml"
check "deploy-inference.yml installs contracts + common" \
    "grep -q 'pip install -e contracts/python' $PROJECT_ROOT/.github/workflows/deploy-inference.yml && grep -q 'pip install -e common/python' $PROJECT_ROOT/.github/workflows/deploy-inference.yml"
check "deploy-plugin.yml installs contracts + common" \
    "grep -q 'pip install -e contracts/python' $PROJECT_ROOT/.github/workflows/deploy-plugin.yml && grep -q 'pip install -e common/python' $PROJECT_ROOT/.github/workflows/deploy-plugin.yml"
echo ""

# Section 5: CI workflows trigger paths
echo "5. CI workflows trigger on contracts changes"
echo "------------------------------------------------------------"
check "deploy-backend.yml triggers on contracts/**" \
    "grep -q '\"contracts/\*\*\"' $PROJECT_ROOT/.github/workflows/deploy-backend.yml"
check "deploy-inference.yml triggers on contracts/**" \
    "grep -q '\"contracts/\*\*\"' $PROJECT_ROOT/.github/workflows/deploy-inference.yml"
check "deploy-plugin.yml triggers on contracts/**" \
    "grep -q '\"contracts/\*\*\"' $PROJECT_ROOT/.github/workflows/deploy-plugin.yml"
check "deploy-frontend.yml triggers on contracts/**" \
    "grep -q '\"contracts/\*\*\"' $PROJECT_ROOT/.github/workflows/deploy-frontend.yml"
echo ""

# Section 6: docker-compose.yml
echo "6. docker-compose.yml build context"
echo "------------------------------------------------------------"
check "docker-compose.yml backend uses context: ../" \
    "grep -A2 'build:' $PROJECT_ROOT/docker/docker-compose.yml | grep -q 'context: \.\./'"
check "docker-compose.yml backend uses dockerfile: backend/Dockerfile" \
    "grep -q 'dockerfile: backend/Dockerfile' $PROJECT_ROOT/docker/docker-compose.yml"
check "docker-compose.yml inference uses dockerfile: inference/Dockerfile" \
    "grep -q 'dockerfile: inference/Dockerfile' $PROJECT_ROOT/docker/docker-compose.yml"
check "docker-compose.yml plugin uses dockerfile: plugin/Dockerfile" \
    "grep -q 'dockerfile: plugin/Dockerfile' $PROJECT_ROOT/docker/docker-compose.yml"
check "docker-compose.yml frontend uses dockerfile: frontend/Dockerfile" \
    "grep -q 'dockerfile: frontend/Dockerfile' $PROJECT_ROOT/docker/docker-compose.yml"
echo ""

# Section 7: Frontend contracts dependency
echo "7. Frontend contracts dependency"
echo "------------------------------------------------------------"
check "frontend/package.json has @taskingai/contracts" \
    "grep -q '\"@taskingai/contracts\": \"file:../contracts/npm\"' $PROJECT_ROOT/frontend/package.json"
check "frontend/package-lock.json has @taskingai/contracts" \
    "grep -q '\"@taskingai/contracts\"' $PROJECT_ROOT/frontend/package-lock.json"
echo ""

# Section 8: Common module structure
echo "8. Common module (tkhelper) structure"
echo "------------------------------------------------------------"
check "common/python/tkhelper exists" \
    "[ -d $PROJECT_ROOT/common/python/tkhelper ]"
check "common/python/pyproject.toml exists" \
    "[ -f $PROJECT_ROOT/common/python/pyproject.toml ]"
check "backend/tkhelper is symlink" \
    "[ -L $PROJECT_ROOT/backend/tkhelper ]"
echo ""

# Section 9: Scripts
echo "9. Build scripts"
echo "------------------------------------------------------------"
check "scripts/build.sh exists" \
    "[ -f $PROJECT_ROOT/scripts/build.sh ]"
check "scripts/setup-dev.sh exists" \
    "[ -f $PROJECT_ROOT/scripts/setup-dev.sh ]"
check "scripts/check-contracts.sh exists" \
    "[ -f $PROJECT_ROOT/scripts/check-contracts.sh ]"
check "scripts/setup-dev.sh installs common/python" \
    "grep -q 'pip install -e .*common/python' $PROJECT_ROOT/scripts/setup-dev.sh"
echo ""

# Section 10: Root .dockerignore
echo "10. Root .dockerignore"
echo "------------------------------------------------------------"
check ".dockerignore exists at project root" \
    "[ -f $PROJECT_ROOT/.dockerignore ]"
echo ""

# Summary
echo "============================================================"
echo "Summary: $PASSED passed, $FAILED failed"
echo "============================================================"

if [ "$FAILED" -eq 0 ]; then
    echo ""
    echo "✓ All build consistency checks passed!"
    echo ""
    exit 0
else
    echo ""
    echo "✗ Some checks failed. Please review the output above."
    echo ""
    exit 1
fi
