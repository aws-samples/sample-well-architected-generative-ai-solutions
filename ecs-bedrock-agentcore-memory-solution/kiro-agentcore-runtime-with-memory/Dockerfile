# Kiro CLI + MCP as AgentCore Runtime (ARM64)
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN dnf upgrade -y --security && \
    dnf install -y python3.13 python3.13-pip bash unzip tar gzip shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

# Install AWS CLI (curl-minimal is pre-installed in AL2023)
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscli.zip && \
    unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

# Install Kiro CLI via official installer
ENV HOME=/root
RUN curl -fsSL https://cli.kiro.dev/install | bash

# Verify installations
RUN kiro-cli --version && aws --version

# Install bedrock-agentcore SDK
RUN python3 -m pip install --no-cache-dir bedrock-agentcore

# Copy the HTTP/ACP wrapper
COPY wrapper.py /app/wrapper.py
COPY profiles/ /app/profiles/

ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "/app/wrapper.py"]
