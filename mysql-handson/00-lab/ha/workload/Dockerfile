FROM python:3.12.13-slim-bookworm

WORKDIR /app
COPY workload/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY workload /app/workload
COPY verifier /app/verifier
COPY tests /app/tests
COPY Makefile /app/Makefile
COPY compose.yml /app/compose.yml
COPY config /app/config
COPY init /app/init
COPY bootstrap /app/bootstrap
COPY faults /app/faults
COPY scenarios /app/scenarios
COPY tools /app/tools
ENV PYTHONPATH=/app
CMD ["python", "-m", "workload.runner", "--help"]
