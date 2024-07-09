FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.8.3  \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/setup"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

FROM base as builder

RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes pipx
ENV PATH="/root/.local/bin:${PATH}"
RUN pipx install poetry
WORKDIR $PYSETUP_PATH
COPY price-pusher/pyproject.toml price-pusher/poetry.lock /opt/setup/
RUN mkdir -p /opt/pragma-sdk
RUN mkdir -p /opt/pragma-utils
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
RUN poetry env use 3.12
RUN poetry install

FROM base as final
COPY --from=builder $PYSETUP_PATH $PYSETUP_PATH
COPY --from=builder /opt/pragma-sdk /opt/pragma-sdk
COPY --from=builder /opt/pragma-utils /opt/pragma-utils
COPY price-pusher/ /price-pusher/
WORKDIR /price-pusher
ENTRYPOINT ["tail", "-f", "/dev/null"]