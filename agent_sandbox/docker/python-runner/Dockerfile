FROM python:3.12-slim

RUN pip install --no-cache-dir pytest pytest-json-report
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner

WORKDIR /workspace
USER runner