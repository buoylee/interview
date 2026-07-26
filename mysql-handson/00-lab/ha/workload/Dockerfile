FROM python:3.12.13-slim-bookworm

WORKDIR /app
COPY workload/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY workload /app/workload
COPY tests /app/tests
ENV PYTHONPATH=/app
CMD ["python", "-m", "workload.runner", "--help"]
