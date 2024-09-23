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
RUN apt-get update && apt-get install -y bash curl && curl -1sLf \
'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' | bash \
&& apt-get update && apt-get install -y infisical

RUN pipx install poetry
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY checkpointer/ /opt/checkpointer/
WORKDIR /opt/checkpointer
RUN poetry env use 3.12
RUN poetry install

FROM base as final
COPY --from=builder /usr/bin/infisical /usr/bin/infisical
COPY --from=builder /opt /opt
COPY infra/checkpointer/config/ /opt/checkpointer/config/
COPY infra/checkpointer/entrypoint.sh /opt/checkpointer/
WORKDIR /opt/checkpointer
ENTRYPOINT ["bash","/opt/checkpointer/entrypoint.sh"]
