FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g npx

WORKDIR /app

COPY pyproject.toml README.md .env ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[dev]"

ENV SENTINEL_DEMO_MODE=true
ENV GEMINI_MODEL=gemini-2.0-flash
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["sentinel"]

CMD ["interactive", "--demo"]
