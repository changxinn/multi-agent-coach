FROM python:3.12-slim

WORKDIR /bootstrap
RUN adduser --disabled-password --gecos '' appuser
COPY services/database_bootstrap/requirements.lock .
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock
COPY services/database_bootstrap/bootstrap.py .
USER appuser
CMD ["python", "bootstrap.py"]