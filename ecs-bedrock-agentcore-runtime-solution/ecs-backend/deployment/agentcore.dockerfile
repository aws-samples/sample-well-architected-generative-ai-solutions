# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# AgentCore Backend - Multi-stage build on Amazon Linux 2023

FROM public.ecr.aws/amazonlinux/amazonlinux:2023 AS builder
ARG DEBIAN_FRONTEND=noninteractive
RUN dnf install -y python3.12 python3.12-pip python3.12-devel gcc shadow-utils && dnf clean all
WORKDIR /build
COPY requirements.txt .
RUN python3.12 -m pip install --user --no-cache-dir --upgrade pip && \
    python3.12 -m pip install --user --no-cache-dir -r requirements.txt

FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN dnf install -y python3.12 shadow-utils findutils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
RUN groupadd -r agentcore && useradd -r -g agentcore agentcore
WORKDIR /app
COPY --from=builder /root/.local /home/agentcore/.local
COPY . .
RUN mkdir -p /app/logs /app/cache /app/tmp && \
    chown -R agentcore:agentcore /app && \
    chmod -R 755 /app
USER agentcore

ENV PATH=/home/agentcore/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BACKEND_MODE=agentcore \
    LOG_LEVEL=INFO \
    ENABLE_STRANDS_AGENTS=true \
    ENABLE_AGENTCORE_RUNTIME=true \
    ENABLE_GRACEFUL_DEGRADATION=true \
    PARAM_PREFIX=coa

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python3", "-c", "from main import create_app; app = create_app(); import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000, workers=1)"]

LABEL maintainer="AWS Cloud Optimization Assistant Team" \
      version="1.0.0" \
      description="COA AgentCore Backend - Strands Agents with Bedrock AgentCore Runtime"
