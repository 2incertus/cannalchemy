# Stage 1: Build frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

# Stage 2: Python API + nginx
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

# App code + deps (hatchling needs the package dir to resolve)
WORKDIR /app
COPY pyproject.toml README.md ./
COPY cannalchemy/ ./cannalchemy/
RUN pip install --no-cache-dir '.[ml,api]'

# Pre-built frontend
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# nginx config
COPY deploy/nginx.conf /etc/nginx/sites-available/default

# supervisord config
COPY deploy/supervisord.conf /etc/supervisor/conf.d/cannalchemy.conf

# Data directory (mounted at runtime)
RUN mkdir -p /app/data/processed /app/data/models/v2

EXPOSE 8080

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/cannalchemy.conf"]
