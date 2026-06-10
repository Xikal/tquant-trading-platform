ARG NODE_BASE_IMAGE=docker.m.daocloud.io/library/node:20-bookworm-slim
ARG RUST_BASE_IMAGE=docker.m.daocloud.io/library/rust:1.95-bookworm
ARG PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-slim

FROM ${NODE_BASE_IMAGE} AS frontend-next-builder

WORKDIR /app/frontend-next

COPY frontend-next/package*.json ./
RUN npm ci

COPY frontend-next/ ./
RUN npm run build


FROM ${RUST_BASE_IMAGE} AS rust-builder

ARG DEBIAN_APT_MIRROR=""
ARG DEBIAN_APT_SECURITY_MIRROR=""

WORKDIR /app/rust/tquant-rs

RUN if [ -n "$DEBIAN_APT_SECURITY_MIRROR" ]; then \
        sed -i "s|http://deb.debian.org/debian-security|$DEBIAN_APT_SECURITY_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && if [ -n "$DEBIAN_APT_MIRROR" ]; then \
        sed -i "s|http://deb.debian.org/debian|$DEBIAN_APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3-dev python3-pip \
    && pip3 install --break-system-packages --no-cache-dir --retries 20 --timeout 600 --progress-bar off -i https://pypi.tuna.tsinghua.edu.cn/simple maturin \
    && mkdir -p /usr/local/cargo \
    && printf '[source.crates-io]\nreplace-with = "rsproxy-sparse"\n\n[source.rsproxy-sparse]\nregistry = "sparse+https://rsproxy.cn/index/"\n' > /usr/local/cargo/config.toml \
    && rm -rf /var/lib/apt/lists/*

COPY rust/tquant-rs/ ./
RUN PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin build --release --locked --strip --features extension-module -o /tmp/wheels


FROM ${PYTHON_BASE_IMAGE} AS runtime

ARG DEBIAN_APT_MIRROR=""
ARG DEBIAN_APT_SECURITY_MIRROR=""

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DEFAULT_TIMEOUT=120

WORKDIR /app/backend

RUN if [ -n "$DEBIAN_APT_SECURITY_MIRROR" ]; then \
        sed -i "s|http://deb.debian.org/debian-security|$DEBIAN_APT_SECURITY_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && if [ -n "$DEBIAN_APT_MIRROR" ]; then \
        sed -i "s|http://deb.debian.org/debian|$DEBIAN_APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --retries 8 -r /tmp/backend-requirements.txt
COPY --from=rust-builder /tmp/wheels/*.whl /tmp/
RUN pip install /tmp/*.whl && rm -f /tmp/*.whl

ARG INSTALL_RL_EXTRAS=0
ARG WITH_RL=0
COPY backend/requirements-rl-extra.txt /tmp/backend-requirements-rl-extra.txt
RUN if [ "$INSTALL_RL_EXTRAS" = "1" ] || [ "$WITH_RL" = "1" ] || [ "$WITH_RL" = "true" ]; then \
        pip install --retries 8 -r /tmp/backend-requirements-rl-extra.txt; \
    fi

ARG INSTALL_ANALYTICS=0
COPY backend/requirements-analytics.txt /tmp/backend-requirements-analytics.txt
RUN if [ "$INSTALL_ANALYTICS" = "1" ] || [ "$INSTALL_ANALYTICS" = "true" ]; then \
        pip install --retries 8 -r /tmp/backend-requirements-analytics.txt; \
    fi

COPY backend /app/backend
COPY scripts /app/scripts
COPY docs/reports/strategy-24m-backtest-2026-05-30.json /app/docs/reports/strategy-24m-backtest-2026-05-30.json
COPY docs/reports/focus-strategy-walk-forward-plan-2026-05-28/summary.json /app/docs/reports/focus-strategy-walk-forward-plan-2026-05-28/summary.json
COPY docs/reports/focus-strategy-parameter-walk-forward-2026-05-28/summary.json /app/docs/reports/focus-strategy-parameter-walk-forward-2026-05-28/summary.json
COPY --from=frontend-next-builder /app/frontend-next/dist /app/frontend-next/dist

RUN adduser --disabled-password --gecos "" --home /home/tquant tquant \
    && mkdir -p /app/backend/data \
    && chown -R tquant:tquant /app/backend /app/frontend-next /app/scripts /app/docs

USER tquant

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker -w \"${APP_WORKERS:-1}\" --bind 0.0.0.0:8000 app.main:app"]
