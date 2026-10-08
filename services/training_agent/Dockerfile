FROM python:3.12-slim

WORKDIR /service
RUN adduser --disabled-password --gecos '' appuser
COPY services/training_agent/requirements.lock .
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock
COPY services/training_agent/app /service/app
USER appuser
EXPOSE 8005
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]