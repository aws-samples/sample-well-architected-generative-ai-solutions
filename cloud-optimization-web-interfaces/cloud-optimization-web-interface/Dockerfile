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
# CONNECTION WITH SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Multi-stage build for production optimization
# Build stage - Install dependencies
FROM public.ecr.aws/amazonlinux/amazonlinux:2023 as builder

# Install Python 3.11 and build dependencies
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    gcc-c++ \
    make \
    && dnf clean all

# Create build directory
WORKDIR /build

# Copy requirements first for better layer caching
COPY backend/requirements.txt .

# Install Python dependencies to user directory
RUN pip3.11 install --user --no-cache-dir --upgrade pip && \
    pip3.11 install --user --no-cache-dir -r requirements.txt

# Production stage - Minimal runtime image
FROM public.ecr.aws/amazonlinux/amazonlinux:2023 as production

# Install only runtime dependencies
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    shadow-utils \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && rpm -e --nodeps curl-minimal libcurl-minimal 2>/dev/null || true

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY backend/ .

# Create necessary directories and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose application port
EXPOSE 8000

# Add health check using Python instead of curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3.11 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
