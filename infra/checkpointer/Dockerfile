FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

ENV PATH="/root/.local/bin:${PATH}"

FROM base as builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gcc \
    curl \
    libgmp3-dev \
    pipx


RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY checkpointer/ /opt/checkpointer/
WORKDIR /opt/checkpointer
RUN uv sync --all-extras

FROM base as final
COPY --from=builder /opt /opt
COPY infra/checkpointer/config/ /opt/checkpointer/config/
COPY infra/checkpointer/entrypoint.sh /opt/checkpointer/
WORKDIR /opt/checkpointer

# Expose the port that your application will listen on
EXPOSE 8081

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://0.0.0.0:8081/ || exit 1

ENTRYPOINT ["bash","/opt/checkpointer/entrypoint.sh"]
