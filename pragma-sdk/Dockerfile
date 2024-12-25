FROM python:3.12-slim-bullseye AS base

# Install dependencies and uv
RUN apt-get update && \
    apt-get install -y gcc python-dev libgmp3-dev curl && \
    apt-get clean && \
    python -m pip install --upgrade pip && \
    curl -LsSf https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh | sh && \
    echo 'export PATH="/root/.local/bin:$PATH"' >> ~/.bashrc && \
    . ~/.bashrc

WORKDIR /app/

COPY ./pragma-sdk /app/
RUN /root/.local/bin/uv sync --all-extras

FROM base AS test

FROM base AS production
ARG PRAGMA_PACKAGE_VERSION
RUN pip install pragma-sdk==$PRAGMA_PACKAGE_VERSION --no-cache-dir --use-deprecated=legacy-resolver
