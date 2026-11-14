# Stage 1: build the React interface
FROM node:20-slim AS ui
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python backend, which also serves the built interface
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY --from=ui /app/frontend/dist frontend/dist

WORKDIR /app/backend
ENV ANALYST_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health')"
# hosts such as Render and Railway tell the app which port to use through $PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
