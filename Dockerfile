# Build the Vite app with a Node version supported by Vite 8.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Serve the API and built SPA together, matching the production layout in README.md.
FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --disable-pip-version-check -r /tmp/requirements.txt \
    && addgroup --system app \
    && adduser --system --ingroup app --no-create-home app

COPY backend/server/ /app/backend/server/
COPY --from=frontend-build /src/frontend/dist/ /app/frontend/dist/

USER app
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn server.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
