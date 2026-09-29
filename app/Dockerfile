# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12

# --- Etapa 1: genera la base de datos SQLite con Faker ---
FROM python:${PYTHON_VERSION}-slim AS seed
WORKDIR /build
COPY requirements-seed.txt .
RUN pip install --no-cache-dir -r requirements-seed.txt
COPY seed/ seed/
RUN python -m seed.generate --output /build/infra.db

# --- Etapa 2: imagen final, sin Faker ni herramientas de build ---
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/infra.db \
    APP_VERSION=${APP_VERSION}

# UID numérico: permite que Kubernetes verifique runAsNonRoot.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY --from=seed /build/infra.db data/infra.db

USER 10001
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
