# ── Stage 1: Build Next.js ───────────────────────────────────────────────────
FROM node:20-alpine AS nextjs-builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY app ./app
COPY public ./public
COPY next.config.ts tsconfig.json postcss.config.* tailwind.config.* ./

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# Install Node.js 20 + supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        supervisor \
        fonts-liberation2 \
        fonts-open-sans \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project source
COPY . .

# Bring in Next.js build artifacts and node_modules from builder stage
COPY --from=nextjs-builder /app/.next ./.next
COPY --from=nextjs-builder /app/node_modules ./node_modules

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV NEXT_TELEMETRY_DISABLED=1
# FastAPI runs internally on 8000; Next.js proxies /api/* to it
ENV BACKEND_URL=http://localhost:8000

# Azure App Service routes external traffic to this port (set WEBSITES_PORT=3000)
EXPOSE 3000

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
