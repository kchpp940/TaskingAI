#!/usr/bin/env bash
# ============================================================
# TaskingAI Build Script
# ============================================================
# Build Docker images for all services from project root context.
#
# Usage:
#   ./scripts/build.sh backend          # Build backend image
#   ./scripts/build.sh inference        # Build inference image
#   ./scripts/build.sh plugin           # Build plugin image
#   ./scripts/build.sh frontend         # Build frontend image
#   ./scripts/build.sh all              # Build all images
#
# Build context is always the project root directory.
# Each service's Dockerfile is located at <service>/Dockerfile
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_TAG="${IMAGE_TAG:-latest}"

build_service() {
    local service="$1"
    local dockerfile="$PROJECT_ROOT/$service/Dockerfile"

    if [ ! -f "$dockerfile" ]; then
        echo "ERROR: Dockerfile not found for service '$service' at $dockerfile"
        exit 1
    fi

    echo "============================================================"
    echo "Building: $service"
    echo "Dockerfile: $dockerfile"
    echo "Build context: $PROJECT_ROOT"
    echo "Image tag: taskingai-$service:$IMAGE_TAG"
    echo "============================================================"

    cd "$PROJECT_ROOT"
    docker build \
        -f "$dockerfile" \
        -t "taskingai-$service:$IMAGE_TAG" \
        .

    echo ""
    echo "✓ Successfully built taskingai-$service:$IMAGE_TAG"
    echo ""
}

case "${1:-all}" in
    backend)
        build_service "backend"
        ;;
    inference)
        build_service "inference"
        ;;
    plugin)
        build_service "plugin"
        ;;
    frontend)
        build_service "frontend"
        ;;
    all)
        build_service "backend"
        build_service "inference"
        build_service "plugin"
        build_service "frontend"
        ;;
    *)
        echo "Usage: $0 {backend|inference|plugin|frontend|all}"
        exit 1
        ;;
esac
