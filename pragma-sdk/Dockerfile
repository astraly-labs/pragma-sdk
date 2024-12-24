# Dockerfile for publisher
FROM python:3.12-slim-bullseye AS base

# Needed for fastecdsa
RUN apt-get update && apt-get install -y gcc python-dev libgmp3-dev curl && apt-get clean
RUN python -m pip install --upgrade pip

RUN apt-get update && \
    pipx

# Defaults
WORKDIR /app/

RUN pipx install uv
COPY ./pragma-sdk /app/
RUN uv sync --all-extras

FROM base as test
# If you have additional test dependencies, install them here.
# Else, you can omit this stage or perform your tests.

FROM base as production
ARG PRAGMA_PACKAGE_VERSION
RUN pip install pragma-sdk==$PRAGMA_PACKAGE_VERSION --no-cache-dir --use-deprecated=legacy-resolver
