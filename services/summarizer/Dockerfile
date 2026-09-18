FROM python:3.12-slim

WORKDIR /service

RUN adduser --disabled-password --gecos '' appuser

COPY services/summarizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents /service/agents
COPY display.py /service/display.py
COPY utils.py /service/utils.py
COPY services/summarizer/app /service/app

ENV PYTHONPATH=/service
ENV SUMMARIZER_SERVICE_MODE=true

USER appuser

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
