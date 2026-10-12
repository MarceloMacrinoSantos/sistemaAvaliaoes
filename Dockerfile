# ---- 1) compila o frontend Vue ----
FROM node:20-alpine AS front
WORKDIR /front
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 2) backend Python servindo API + frontend ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 FRONTEND_DIST=/app/frontend/dist
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=front /front/dist frontend/dist
WORKDIR /app/backend
EXPOSE 8000
# 1 worker é suficiente para dezenas de alunos; aumente WEB_CONCURRENCY se a máquina tiver mais CPU
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --proxy-headers"]
