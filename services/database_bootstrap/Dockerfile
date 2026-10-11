FROM python:3.12-slim

WORKDIR /bootstrap
RUN adduser --disabled-password --gecos '' appuser
COPY services/database_bootstrap/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/database_bootstrap/bootstrap.py .
USER appuser
CMD ["python", "bootstrap.py"]