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
    libgmp3-dev \
    curl \
    pipx

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY price-pusher/ /opt/price-pusher/
WORKDIR /opt/price-pusher
RUN uv sync --all-extras

FROM base as final

# Install curl for health checks
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt /opt
COPY infra/price-pusher/pragma/entrypoint.sh /opt/price-pusher/
COPY infra/price-pusher/config/ /opt/price-pusher/config/
WORKDIR /opt/price-pusher

EXPOSE 8083

# Add healthcheck using the new FastAPI health endpoints
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://0.0.0.0:8083/health || exit 1

ENTRYPOINT ["bash","/opt/price-pusher/entrypoint.sh"]
