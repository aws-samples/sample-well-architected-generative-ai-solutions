# syntax=docker/dockerfile:1.7
# hadolint global ignore=DL3041
# Note: DL3041 ignored because Amazon Linux uses rolling releases within major version
# Pin to specific AL2023 release for reproducibility

FROM public.ecr.aws/amazonlinux/amazonlinux:2023.6.20241212.0 AS builder

RUN dnf install -y --setopt=install_weak_deps=False \
    python3.11 python3.11-pip python3.11-devel gcc gcc-c++ make shadow-utils \
    && dnf clean all && rm -rf /var/cache/dnf

RUN useradd -r -m -d /home/builduser -s /sbin/nologin builduser
WORKDIR /home/builduser
USER builduser

COPY --chown=builduser:builduser backend/requirements.txt .

# hadolint ignore=DL3013
# Note: pip version pinned, other versions in requirements.txt
RUN pip3.11 install --user --no-cache-dir pip==24.3.1 && \
    pip3.11 install --user --no-cache-dir -r requirements.txt

FROM public.ecr.aws/amazonlinux/amazonlinux:2023.6.20241212.0 AS production

LABEL maintainer="team@example.com" \
      version="1.0.0"

RUN dnf install -y --setopt=install_weak_deps=False python3.11 shadow-utils \
    && dnf clean all && rm -rf /var/cache/dnf \
    && rpm -e --nodeps curl-minimal libcurl-minimal 2>/dev/null || true \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

RUN groupadd -r -g 1001 appuser && \
    useradd -r -u 1001 -g appuser -d /home/appuser -s /sbin/nologin -m appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /home/builduser/.local /home/appuser/.local
COPY --chown=appuser:appuser backend/ .

RUN mkdir -p /app/logs && chown appuser:appuser /app/logs && chmod 750 /app/logs

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3.11 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)" || exit 1

CMD ["python3.11", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
