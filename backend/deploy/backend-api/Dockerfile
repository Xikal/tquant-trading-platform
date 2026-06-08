ARG BASE_IMAGE=tquant-web:mysql
FROM ${BASE_IMAGE}

USER root
COPY app /app/backend/app
COPY alembic /app/backend/alembic
COPY scripts /app/backend/scripts
COPY alembic.ini /app/backend/alembic.ini
RUN chown -R tquant:tquant /app/backend
USER tquant

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker -w \"${APP_WORKERS:-1}\" --bind 0.0.0.0:8000 app.main:app"]
