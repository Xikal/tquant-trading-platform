FROM docker.m.daocloud.io/library/node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM docker.m.daocloud.io/library/python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DEFAULT_TIMEOUT=120

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --retries 8 -r /tmp/backend-requirements.txt

ARG INSTALL_RL_EXTRAS=0
ARG WITH_RL=0
COPY backend/requirements-rl-extra.txt /tmp/backend-requirements-rl-extra.txt
RUN if [ "$INSTALL_RL_EXTRAS" = "1" ] || [ "$WITH_RL" = "1" ] || [ "$WITH_RL" = "true" ]; then \
        pip install --retries 8 -r /tmp/backend-requirements-rl-extra.txt; \
    fi

COPY backend /app/backend
COPY scripts /app/scripts
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN adduser --disabled-password --gecos "" --home /home/tquant tquant \
    && mkdir -p /app/backend/data \
    && chown -R tquant:tquant /app/backend /app/frontend /app/scripts

USER tquant

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--bind", "0.0.0.0:8000", "app.main:app"]
