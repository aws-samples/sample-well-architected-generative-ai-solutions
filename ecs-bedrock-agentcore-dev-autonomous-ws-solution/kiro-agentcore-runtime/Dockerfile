# Kiro CLI + MCP as AgentCore Runtime (ARM64)
FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get upgrade -y && apt-get install -y curl bash unzip coreutils && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscli.zip && \
    unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

# Install uv (for uvx to run aws-api-mcp-server)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Pre-install aws-api-mcp-server so it's cached in the image
RUN uvx --from "awslabs.aws-api-mcp-server@latest" awslabs.aws-api-mcp-server --help || true

# Install GitHub CLI (ARM64)
RUN GH_VER=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | python3 -c "import sys,json;print(json.load(sys.stdin)['tag_name'][1:])") && \
    curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_arm64.tar.gz" \
    | tar xz -C /tmp && cp /tmp/gh_*/bin/gh /usr/local/bin/ && rm -rf /tmp/gh_*

# Install Kiro CLI via official installer
ENV HOME=/root
RUN curl -fsSL https://cli.kiro.dev/install | bash

# Verify installations
RUN kiro-cli --version && aws --version && gh --version

# Install bedrock-agentcore SDK and aws-api-mcp-server
RUN pip install --no-cache-dir bedrock-agentcore "awslabs.aws-api-mcp-server"

# Copy the HTTP/ACP wrapper
COPY wrapper.py /app/wrapper.py
COPY profiles/ /app/profiles/

ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "/app/wrapper.py"]
