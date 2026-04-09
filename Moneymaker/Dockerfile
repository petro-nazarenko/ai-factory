FROM python:3.11-slim

WORKDIR /app

# System deps (for asyncpg, praw)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Data dir for SQLite fallback (dev mode)
RUN mkdir -p /app/data

# Default: API server (overridden per-service in docker-compose.yml)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
