FROM python:3.12-slim

WORKDIR /service

RUN adduser --disabled-password --gecos '' appuser

COPY services/recovery_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/recovery_agent/app ./app
COPY ../../app/db/migration_runner.py ./app/migration_runner.py

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
