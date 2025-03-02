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
    g++ \
    libssl-dev \
    curl \
    swig \
    libgmp3-dev \
    pkg-config \
    pipx \
    stunnel4

RUN apt-get update && apt-get install -y bash curl

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY lmax-connector/ /opt/lmax-connector/
COPY lmax-connector/config/Fix44.xml /opt/lmax-connector/config/Fix44.xml
WORKDIR /opt/lmax-connector
RUN uv sync

FROM base as final

COPY --from=builder /usr/bin/stunnel /usr/bin/stunnel
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /opt /opt
COPY infra/lmax-connector/entrypoint.sh /opt/lmax-connector/
WORKDIR /opt/lmax-connector

# Add a healthcheck for Kubernetes compatibility
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://0.0.0.0:8080/ || exit 1

EXPOSE 8080

ENTRYPOINT ["bash", "/opt/lmax-connector/entrypoint.sh"]
