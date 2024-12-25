FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

ENV PATH="/root/.local/bin:${PATH}"

FROM base AS builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gcc \
    libgmp3-dev \
    pipx

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY checkpointer/ /opt/checkpointer/
WORKDIR /opt/checkpointer
RUN uv sync --all-extras

FROM base AS final
COPY --from=builder /opt /opt
VOLUME checkpointer/config /opt/checkpointer/config/
WORKDIR /opt/checkpointer
ENTRYPOINT ["/opt/checkpointer/.venv/bin/python3.12", "checkpointer/main.py"]
