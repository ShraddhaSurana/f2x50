FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y gfortran git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /artifact
COPY requirements-harness.txt ./
RUN python -m pip install --no-cache-dir -r requirements-harness.txt
COPY . .

CMD ["bash", "scripts/cleanroom_smoke.sh", "/tmp/f2x50-corpus"]
