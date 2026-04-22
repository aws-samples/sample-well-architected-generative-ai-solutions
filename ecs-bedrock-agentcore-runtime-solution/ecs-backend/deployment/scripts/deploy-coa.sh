#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Deployment script for COA AgentCore Backend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"

DEFAULT_ACTION="deploy"
DEFAULT_ENVIRONMENT="dev"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "${PURPLE}[STEP]${NC} $1"; }

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] ACTION

Deployment script for COA AgentCore Backend

ACTIONS:
  build     Build Docker image only
  deploy    Build and deploy with Docker Compose
  start     Start existing deployment
  stop      Stop running deployment
  restart   Restart deployment
  status    Show deployment status
  logs      Show deployment logs
  clean     Stop and remove containers/images

OPTIONS:
  -e, --env ENV        Environment (dev/staging/prod) [default: dev]
  -t, --tag TAG        Image tag [default: latest]
  --no-cache           Build without cache
  --validate-only      Only validate configuration
  -v, --verbose        Verbose output
  -h, --help           Show this help

EXAMPLES:
  $0 deploy
  $0 build --no-cache
  $0 status
  $0 clean
EOF
}

validate_environment() {
    log_step "Validating deployment environment..."
    command -v docker &>/dev/null || { log_error "Docker not found"; exit 1; }
    command -v docker-compose &>/dev/null || { log_error "Docker Compose not found"; exit 1; }
    [[ -d "${DEPLOYMENT_DIR}" ]] || { log_error "Deployment directory not found: ${DEPLOYMENT_DIR}"; exit 1; }
    [[ -f "${DEPLOYMENT_DIR}/docker-compose.yml" ]] || { log_error "docker-compose.yml not found"; exit 1; }
    [[ -f "${DEPLOYMENT_DIR}/agentcore.dockerfile" ]] || { log_error "agentcore.dockerfile not found"; exit 1; }
    [[ -d "${PROJECT_ROOT}/agentcore" ]] || { log_error "agentcore directory not found"; exit 1; }
    log_success "Environment validation passed"
}

show_status() {
    log_step "Checking AgentCore deployment status..."
    cd "${DEPLOYMENT_DIR}"
    echo ""
    log_info "Container Status:"
    docker-compose --profile agentcore ps
    echo ""
    if docker ps --filter "name=coa-agentcore" --filter "status=running" | grep -q coa-agentcore; then
        log_info "AgentCore: Running (http://localhost:8000/health)"
    else
        log_info "AgentCore: Not running"
    fi
}

# Parse arguments
ACTION="${DEFAULT_ACTION}"
ENVIRONMENT="${DEFAULT_ENVIRONMENT}"
IMAGE_TAG="latest"
BUILD_ARGS=""
VALIDATE_ONLY="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        build|deploy|start|stop|restart|status|logs|clean) ACTION="$1"; shift ;;
        -e|--env) ENVIRONMENT="$2"; shift 2 ;;
        -t|--tag) IMAGE_TAG="$2"; shift 2 ;;
        --no-cache) BUILD_ARGS="${BUILD_ARGS} --no-cache"; shift ;;
        --validate-only) VALIDATE_ONLY="true"; shift ;;
        -v|--verbose) set -x; shift ;;
        -h|--help) show_usage; exit 0 ;;
        *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

main() {
    log_info "COA AgentCore Deployment"
    log_info "Action: ${ACTION} | Environment: ${ENVIRONMENT} | Tag: ${IMAGE_TAG}"

    validate_environment

    [[ "${VALIDATE_ONLY}" == "true" ]] && { log_success "Validation passed"; exit 0; }

    cd "${DEPLOYMENT_DIR}"

    case "${ACTION}" in
        build)
            "${SCRIPT_DIR}/build-agentcore.sh" ${BUILD_ARGS}
            ;;
        deploy)
            "${SCRIPT_DIR}/build-agentcore.sh" ${BUILD_ARGS}
            docker-compose --profile agentcore up -d
            log_step "Validating deployment..."
            if "${SCRIPT_DIR}/validate-deployment.sh" agentcore --timeout 60; then
                log_success "Deployment validation passed"
            else
                log_error "Deployment validation failed"
                exit 1
            fi
            show_status
            ;;
        start)   docker-compose --profile agentcore start; show_status ;;
        stop)    docker-compose --profile agentcore stop ;;
        restart) docker-compose --profile agentcore restart; show_status ;;
        status)  show_status ;;
        logs)    docker-compose --profile agentcore logs -f ;;
        clean)   docker-compose --profile agentcore down --remove-orphans; docker rmi "coa-agentcore:${IMAGE_TAG}" 2>/dev/null || true; log_success "Cleanup done" ;;
        *)       log_error "Unknown action: ${ACTION}"; exit 1 ;;
    esac

    log_success "Done!"
}

main "$@"
