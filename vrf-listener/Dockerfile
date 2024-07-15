FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.8.3  \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

ENV PATH="/root/.local/bin:${PATH}"

FROM base as builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gcc \
    libgmp3-dev \
    pipx

RUN pipx install poetry
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY vrf-listener/ /opt/vrf-listener/
WORKDIR /opt/vrf-listener
RUN poetry env use 3.12
RUN poetry install

FROM base as final
COPY --from=builder /opt /opt
WORKDIR /opt/vrf-listener
ENTRYPOINT ["/opt/vrf-listener/.venv/bin/python3.12", "vrf_listener/main.py"]