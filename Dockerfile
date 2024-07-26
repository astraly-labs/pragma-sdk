# Dockerfile for publisher
FROM python:3.11-slim-buster AS base

# Needed for fastecdsa
RUN apt-get update && apt-get install -y gcc python-dev libgmp3-dev curl && apt-get clean
RUN python -m pip install --upgrade pip

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"

# Defaults
WORKDIR /app/
COPY . /app/
RUN poetry install

FROM base as test
# If you have additional test dependencies, install them here.
# Else, you can omit this stage or perform your tests.

FROM base as production
ARG PRAGMA_PACKAGE_VERSION
RUN pip install pragma-sdk==$PRAGMA_PACKAGE_VERSION --no-cache-dir --use-deprecated=legacy-resolver