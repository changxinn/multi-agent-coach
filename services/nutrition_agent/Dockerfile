FROM python:3.12-slim

WORKDIR /service

RUN adduser --disabled-password --gecos '' appuser

COPY services/nutrition_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/nutrition_agent/app /service/app

USER appuser

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]