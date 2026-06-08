ARG BASE_IMAGE=tquant-web:mysql
FROM ${BASE_IMAGE}

USER root
COPY backend /app/backend
COPY scripts /app/scripts
RUN chown -R tquant:tquant /app/backend /app/scripts
USER tquant

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker -w \"${APP_WORKERS:-1}\" --bind 0.0.0.0:8000 app.main:app"]
