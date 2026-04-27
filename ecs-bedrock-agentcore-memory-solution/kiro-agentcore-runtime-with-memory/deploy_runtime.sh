#!/bin/bash
set -euo pipefail

# Deploy Kiro AgentCore Runtime
# Usage: ./deploy_runtime.sh [--profile profiles/default.json] [--region us-west-2]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${PROFILE:-$SCRIPT_DIR/profiles/default.json}"
REGION="${REGION:-us-west-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/kiro-agentcore"
CODEBUILD_PROJECT="${CODEBUILD_PROJECT:-sandbox-kiro-agentcore-build}"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile) PROFILE="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

echo "=== Kiro AgentCore Runtime Deploy ==="
echo "Profile: $PROFILE"
echo "Region:  $REGION"
echo "ECR:     $ECR_REPO"

# Step 1: Validate profile
echo ""
echo "--- Step 1: Validate profile ---"
if [ ! -f "$PROFILE" ]; then
  echo "ERROR: Profile not found: $PROFILE"; exit 1
fi

PACKAGES=$(python3 -c "
import json, sys
with open('$PROFILE') as f:
    p = json.load(f)
pkgs = [i['package'] for i in p.get('integrations', []) if i.get('enabled') and i.get('package')]
if not pkgs:
    print('ERROR: No enabled integrations with packages', file=sys.stderr); sys.exit(1)
print(' '.join(pkgs))
")
echo "Packages to install: $PACKAGES"

ENABLED=$(python3 -c "
import json
with open('$PROFILE') as f:
    p = json.load(f)
for i in p.get('integrations', []):
    status = '✓' if i.get('enabled') else '✗'
    print(f\"  {status} {i['name']}: {i.get('description', '')}\")
")
echo "Integrations:"
echo "$ENABLED"

# Step 2: Generate Dockerfile
echo ""
echo "--- Step 2: Generate Dockerfile ---"
DOCKERFILE="$SCRIPT_DIR/Dockerfile.generated"
cat > "$DOCKERFILE" << DOCKEREOF
# Auto-generated from profile: $(basename $PROFILE)
FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y curl bash unzip coreutils && rm -rf /var/lib/apt/lists/*

# AWS CLI
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscli.zip && \\
    unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

# Kiro CLI
ENV HOME=/root
RUN curl -fsSL https://cli.kiro.dev/install | bash

# Pre-install MCP server packages (from profile)
RUN pip install --no-cache-dir bedrock-agentcore $PACKAGES

# Verify
RUN kiro-cli --version && aws --version

COPY wrapper.py /app/wrapper.py
COPY profiles/ /app/profiles/

ENV PORT=8080 PYTHONUNBUFFERED=1 INTEGRATION_PROFILE=/app/profiles/$(basename $PROFILE)
EXPOSE 8080
CMD ["python3", "/app/wrapper.py"]
DOCKEREOF

echo "Generated: $DOCKERFILE"
echo "Validating syntax..."
docker build --check -f "$DOCKERFILE" "$SCRIPT_DIR" 2>/dev/null || true

# Step 3: Build via CodeBuild (or local docker)
echo ""
echo "--- Step 3: Build & Push ---"
if [ "${LOCAL_BUILD:-}" = "true" ]; then
  echo "Building locally..."
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REPO"
  docker buildx build --platform linux/arm64 -f "$DOCKERFILE" -t "$ECR_REPO:latest" --push "$SCRIPT_DIR"
else
  echo "Packaging source for CodeBuild..."
  TMPZIP="/tmp/kiro-runtime-source.zip"
  (cd "$SCRIPT_DIR" && cp "$DOCKERFILE" Dockerfile && zip -r "$TMPZIP" Dockerfile wrapper.py profiles/)
  aws s3 cp "$TMPZIP" "s3://sandbox-coa-agentcore-${ACCOUNT_ID}-${REGION}/kiro-agentcore-build/source.zip" --region "$REGION"
  echo "Starting CodeBuild..."
  BUILD_ID=$(aws codebuild start-build --project-name "$CODEBUILD_PROJECT" --region "$REGION" --query "build.id" --output text)
  echo "Build started: $BUILD_ID"
  echo "Waiting for build..."
  aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" --query "builds[0].buildStatus" --output text
  # Poll until complete
  while true; do
    STATUS=$(aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" --query "builds[0].buildStatus" --output text)
    echo "  Status: $STATUS"
    [ "$STATUS" != "IN_PROGRESS" ] && break
    sleep 15
  done
  [ "$STATUS" != "SUCCEEDED" ] && echo "ERROR: Build failed" && exit 1
fi

echo ""
echo "=== Build complete ==="
echo "Image: $ECR_REPO:latest"
echo ""
echo "To refresh the AgentCore runtime, re-register or restart it."
