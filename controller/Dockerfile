FROM python:3.12-slim

WORKDIR /runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io docker-compose \
    && rm -rf /var/lib/apt/lists/*
COPY controller/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV PYTHONPATH=/runtime
CMD ["uvicorn", "controller.app:app", "--host", "0.0.0.0", "--port", "8080"]
