FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN dnf upgrade -y --security && \
    dnf install -y python3.13 python3.13-pip shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1
WORKDIR /app

COPY requirements.txt requirements.txt
RUN python3.13 -m pip install --no-cache-dir -r requirements.txt
RUN python3.13 -m pip install --no-cache-dir aws-opentelemetry-distro>=0.10.1

ENV AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 DOCKER_CONTAINER=1

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080 8000
COPY . .
CMD ["opentelemetry-instrument", "python3", "-m", "main"]
