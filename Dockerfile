# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the Arena Hot Tips tool.
#
# Stages:
#   frontend-build  - npm install + vite build (produces /app/dist)
#   frontend-dev    - Vite dev server for `docker compose up`
#   backend-base    - Python 3.13 + uv + project dependencies (no app source)
#   backend-dev     - Django dev server using bind-mounted source
#   prod            - Final runtime: backend + built React, gunicorn + whitenoise
#
# Build targets explicitly via `docker build --target <name>` or via compose.

# --------- Frontend build stage ---------
FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --------- Frontend dev stage ---------
FROM node:22-alpine AS frontend-dev
WORKDIR /app
ENV NODE_ENV=development
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --------- Backend base (Python + uv, no project deps yet) ---------
FROM python:3.13-slim-bookworm AS backend-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock* /app/

# --------- Backend dev (full deps including pytest) ---------
FROM backend-base AS backend-dev
RUN uv sync --no-install-project
ENV DJANGO_DEBUG=true \
    DJANGO_SECRET_KEY=dev-insecure-change-me-please
EXPOSE 8000
# Source is bind-mounted at /app by compose. We makemigrations + migrate on
# each start so a fresh checkout boots without a manual setup step. Don't do
# this in production.
CMD ["sh", "-c", "uv run manage.py makemigrations arena --noinput && uv run manage.py migrate --noinput && uv run manage.py runserver 0.0.0.0:8000"]

# --------- Production runtime (runtime deps only) ---------
FROM backend-base AS prod
RUN uv sync --no-install-project --no-default-groups
ENV DJANGO_DEBUG=false \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    PORT=8000
COPY backend/ /app/
COPY --from=frontend-build /app/dist /app/frontend_dist
# Generate the arena migration during the build (the dev container does it at
# startup, but the prod image must be self-contained: no `manage.py
# makemigrations` at runtime).
RUN DJANGO_SECRET_KEY=build-time-only DJANGO_ALLOWED_HOSTS=* \
    uv run python manage.py makemigrations arena --noinput
# collectstatic needs SECRET_KEY since DEBUG=false; we use a build-time
# placeholder that's never used at runtime.
RUN DJANGO_SECRET_KEY=build-time-only DJANGO_ALLOWED_HOSTS=* \
    uv run python manage.py collectstatic --noinput
RUN mkdir -p /data && chmod 777 /data
VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "-c", "uv run manage.py migrate --noinput && exec uv run gunicorn hot_tips.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile -"]
