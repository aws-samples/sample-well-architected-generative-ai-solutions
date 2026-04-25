# Kiro CLI + MCP as AgentCore Runtime (AL2023)
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN dnf install -y python3.12 python3.12-pip unzip tar gzip shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Install AWS CLI
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscli.zip && \
    unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

# Install uv (for uvx to run aws-api-mcp-server)
RUN curl -LsSf https://astral.sh/uv/install.sh | bash
ENV PATH="/root/.local/bin:$PATH"

# Pre-install aws-api-mcp-server so it's cached in the image
RUN uvx --from "awslabs.aws-api-mcp-server@latest" awslabs.aws-api-mcp-server --help || true

# Install Kiro CLI via official installer
ENV HOME=/root
RUN curl -fsSL https://cli.kiro.dev/install | bash

# Verify installations
RUN kiro-cli --version && aws --version

# Install bedrock-agentcore SDK and aws-api-mcp-server
RUN python3.12 -m pip install --no-cache-dir bedrock-agentcore "awslabs.aws-api-mcp-server"

COPY wrapper.py /app/wrapper.py

ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "/app/wrapper.py"]
