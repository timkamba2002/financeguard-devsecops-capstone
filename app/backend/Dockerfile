# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

# Install dependencies and build wheels
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final runtime stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Create a non-privileged user to run the application
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash appuser

# Copy dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local
COPY main.py .

# Adjust permissions
RUN chown -R appuser:appgroup /app

# Set PATH for local pip installation
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
