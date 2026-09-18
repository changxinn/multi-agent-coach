FROM python:3.12-slim

WORKDIR /service

RUN adduser --disabled-password --gecos '' appuser

COPY services/head_coach/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents /service/agents
COPY display.py /service/display.py
COPY utils.py /service/utils.py
COPY services/head_coach/app /service/app

ENV PYTHONPATH=/service
ENV HEAD_COACH_SERVICE_MODE=true

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
