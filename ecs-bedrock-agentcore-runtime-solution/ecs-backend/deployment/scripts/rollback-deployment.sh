#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Rollback script for COA AgentCore Backend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="coa-agentcore"
BACKUP_TAG=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    cat << EOF
Usage: $0 ACTION [OPTIONS]

ACTIONS:
  create-backup    Create a backup of the current image
  rollback         Rollback to a backup image
  list-backups     List available backup images

OPTIONS:
  --backup-tag TAG   Tag for the backup [default: backup-TIMESTAMP]
EOF
}

case "${1:-}" in
    create-backup)
        BACKUP_TAG="${3:-backup-$(date +%Y%m%d-%H%M%S)}"
        if docker image inspect "${IMAGE_NAME}:latest" &>/dev/null; then
            docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:${BACKUP_TAG}"
            log_success "Backup created: ${IMAGE_NAME}:${BACKUP_TAG}"
        else
            log_warning "No current image to backup"
        fi
        ;;
    rollback)
        BACKUP_TAG="${3:-}"
        if [[ -z "${BACKUP_TAG}" ]]; then
            BACKUP_TAG=$(docker images "${IMAGE_NAME}" --format "{{.Tag}}" | grep "^backup-" | head -1)
            [[ -z "${BACKUP_TAG}" ]] && { log_error "No backup found"; exit 1; }
        fi
        log_info "Rolling back to ${IMAGE_NAME}:${BACKUP_TAG}"
        docker tag "${IMAGE_NAME}:${BACKUP_TAG}" "${IMAGE_NAME}:latest"
        cd "${DEPLOYMENT_DIR}" && docker-compose --profile agentcore up -d
        log_success "Rolled back to ${BACKUP_TAG}"
        ;;
    list-backups)
        log_info "Available backups:"
        docker images "${IMAGE_NAME}" --format "  {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | grep "backup-" || echo "  No backups found"
        ;;
    *)
        show_usage
        ;;
esac
