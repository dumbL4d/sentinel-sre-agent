FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g npx

WORKDIR /app

COPY pyproject.toml README.md .env* ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["sentinel-serve"]
