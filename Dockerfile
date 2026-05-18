# Iroko AI — FastAPI Backend
# Builds and runs the AtlasCore API server.
# Frontend is deployed separately on Vercel.

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        fonts-liberation2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (own layer for caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# SQLite DB directory (ephemeral — swap for Postgres in production)
RUN mkdir -p /app/data

# Port the API listens on
EXPOSE 8000

# Seed the database then start the server
CMD ["sh", "-c", "python scripts/seed_all.py || true && uvicorn main:app --host 0.0.0.0 --port 8000"]
