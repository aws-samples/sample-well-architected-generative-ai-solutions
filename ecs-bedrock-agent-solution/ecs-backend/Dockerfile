FROM public.ecr.aws/amazonlinux/amazonlinux:2023 AS builder
WORKDIR /build
RUN dnf install -y python3.12 python3.12-pip shadow-utils && dnf clean all
COPY requirements.txt .
RUN python3.12 -m pip install --user --no-cache-dir -r requirements.txt

FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN dnf install -y python3.12 shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /root/.local /home/app/.local
COPY . .
RUN chown -R app:app /app
USER app
ENV PATH=/home/app/.local/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
