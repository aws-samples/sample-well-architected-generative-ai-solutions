#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Health check script for COA AgentCore Backend

set -e

HEALTH_PORT="${HEALTH_PORT:-8000}"
HEALTH_URL="http://localhost:${HEALTH_PORT}/health"
TIMEOUT="${TIMEOUT:-10}"
EXIT_CODE_MODE="false"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

while [[ $# -gt 0 ]]; do
    case $1 in
        agentcore) shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --port) HEALTH_PORT="$2"; HEALTH_URL="http://localhost:${HEALTH_PORT}/health"; shift 2 ;;
        --exit-code) EXIT_CODE_MODE="true"; shift ;;
        *) shift ;;
    esac
done

response=$(curl -s --max-time "${TIMEOUT}" "${HEALTH_URL}" 2>/dev/null || echo "")

if [[ -z "${response}" ]]; then
    [[ "${EXIT_CODE_MODE}" == "true" ]] && exit 1
    echo -e "${RED}Health check failed: no response from ${HEALTH_URL}${NC}"
    exit 1
fi

status=$(echo "${response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")

case "${status}" in
    healthy)
        [[ "${EXIT_CODE_MODE}" != "true" ]] && echo -e "${GREEN}AgentCore: healthy${NC}"
        exit 0
        ;;
    degraded)
        [[ "${EXIT_CODE_MODE}" != "true" ]] && echo -e "${YELLOW}AgentCore: degraded${NC}"
        exit 0
        ;;
    *)
        [[ "${EXIT_CODE_MODE}" != "true" ]] && echo -e "${RED}AgentCore: ${status}${NC}"
        exit 1
        ;;
esac
