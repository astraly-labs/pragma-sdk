FROM python:3.12-slim-bullseye AS base

# Install dependencies
RUN apt-get update && \
    apt-get install -y gcc python-dev libgmp3-dev curl && \
    apt-get clean && \
    python -m pip install --upgrade pip && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

# Defaults
WORKDIR /app/

# Copy the source code
COPY ./pragma-sdk /app/
RUN uv sync --all-extras

FROM base AS test
# If you have additional test dependencies, install them here.
# Else, you can omit this stage or perform your tests.

FROM base AS production

ARG PRAGMA_PACKAGE_VERSION
RUN pip install pragma-sdk==$PRAGMA_PACKAGE_VERSION --no-cache-dir --use-deprecated=legacy-resolver
