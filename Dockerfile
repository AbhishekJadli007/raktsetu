# ---- build the web app
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- python runtime
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY raktsetu/ raktsetu/
COPY api/ api/
COPY data/ data/
COPY artifacts/ artifacts/
# Models are committed on GitHub; deploy targets that reject binary files rebuild them here (~1 min).
RUN test -f artifacts/forecaster.joblib -a -f artifacts/surge_radar.joblib || python -m raktsetu train
COPY --from=web /web/dist web/dist
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
