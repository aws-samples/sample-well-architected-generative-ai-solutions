#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Deployment validation script for COA AgentCore Backend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DEFAULT_TIMEOUT=60
DEFAULT_RETRY_COUNT=3
CONTAINER_NAME="coa-agentcore"
HEALTH_PORT="8000"

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
Usage: $0 [OPTIONS]

Validate COA AgentCore Backend deployment

OPTIONS:
  -t, --timeout SECONDS   Health check timeout [default: 60]
  -r, --retry COUNT       Retry count [default: 3]
  --skip-health           Skip health check
  --skip-config           Skip configuration validation
  --detailed              Show detailed results
  -h, --help              Show this help
EOF
}

check_container_status() {
    log_step "Checking container status..."
    if docker ps --filter "name=${CONTAINER_NAME}" --filter "status=running" --format "{{.Names}}" | grep -q "${CONTAINER_NAME}"; then
        log_success "Container ${CONTAINER_NAME} is running"
        return 0
    else
        local status=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Status}}" 2>/dev/null || echo "not found")
        log_error "Container ${CONTAINER_NAME} is not running (${status})"
        return 1
    fi
}

check_health_endpoints() {
    log_step "Checking health endpoint..."
    local endpoint="http://localhost:${HEALTH_PORT}/health"
    local retry=0

    while [[ ${retry} -lt ${RETRY_COUNT} ]]; do
        if curl -f -s --max-time "${TIMEOUT}" "${endpoint}" > /dev/null; then
            log_success "Health endpoint responding: ${endpoint}"
            [[ "${DETAILED}" == "true" ]] && curl -s "${endpoint}" | python3 -m json.tool 2>/dev/null || true
            return 0
        fi
        log_warning "Health check attempt $((retry+1))/${RETRY_COUNT} failed, retrying..."
        sleep 5
        ((retry++))
    done

    log_error "Health endpoint failed after ${RETRY_COUNT} attempts"
    return 1
}

validate_configuration() {
    log_step "Validating configuration..."
    local mode=$(docker exec "${CONTAINER_NAME}" python -c "import os; print(os.getenv('BACKEND_MODE', 'unknown'))" 2>/dev/null || echo "error")
    if [[ "${mode}" == "agentcore" ]]; then
        log_success "BACKEND_MODE=agentcore"
    else
        log_warning "BACKEND_MODE=${mode} (expected agentcore)"
    fi
}

check_resource_usage() {
    log_step "Checking resource usage..."
    docker stats "${CONTAINER_NAME}" --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || log_warning "Could not get stats"
}

analyze_logs() {
    log_step "Analyzing logs..."
    local errors=$(docker logs "${CONTAINER_NAME}" --tail 100 2>&1 | grep -ci "error" || echo "0")
    local warnings=$(docker logs "${CONTAINER_NAME}" --tail 100 2>&1 | grep -ci "warning" || echo "0")
    log_info "Recent logs: ${errors} errors, ${warnings} warnings"
    [[ ${errors} -gt 0 ]] && docker logs "${CONTAINER_NAME}" --tail 100 2>&1 | grep -i "error" | tail -3 | sed 's/^/  /'
}

# Parse arguments
TIMEOUT="${DEFAULT_TIMEOUT}"
RETRY_COUNT="${DEFAULT_RETRY_COUNT}"
SKIP_HEALTH="false"
SKIP_CONFIG="false"
DETAILED="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        agentcore) shift ;;  # accept for backward compat, ignore
        -t|--timeout) TIMEOUT="$2"; shift 2 ;;
        -r|--retry) RETRY_COUNT="$2"; shift 2 ;;
        --skip-health) SKIP_HEALTH="true"; shift ;;
        --skip-config) SKIP_CONFIG="true"; shift ;;
        --detailed) DETAILED="true"; shift ;;
        -h|--help) show_usage; exit 0 ;;
        *) shift ;;  # ignore unknown for backward compat
    esac
done

main() {
    log_info "COA AgentCore Deployment Validation"
    local failed=false

    check_container_status || failed=true
    [[ "${SKIP_HEALTH}" != "true" ]] && { check_health_endpoints || failed=true; }
    [[ "${SKIP_CONFIG}" != "true" ]] && validate_configuration
    check_resource_usage
    analyze_logs

    echo ""
    if [[ "${failed}" == "true" ]]; then
        log_error "Validation failed"
        exit 1
    else
        log_success "Validation passed"
    fi
}

main "$@"
