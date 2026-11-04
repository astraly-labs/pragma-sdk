# Built from the repository root:
#   docker build -f validator-publisher/Dockerfile -t validator-publisher .
FROM python:3.12.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
RUN apt-get update && \
    apt-get install --no-install-recommends -y gcc libgmp3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY price-pusher/ /opt/price-pusher/
COPY validator-publisher/ /opt/validator-publisher/
WORKDIR /opt/validator-publisher
# --frozen: the image is exactly the reviewed uv.lock, no Miden client
RUN uv sync --frozen --no-dev --no-editable

FROM base AS final
RUN apt-get update && \
    apt-get install --no-install-recommends -y tini && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin validator
COPY --from=builder /opt/validator-publisher/.venv /opt/validator-publisher/.venv
ENV PATH="/opt/validator-publisher/.venv/bin:${PATH}"
USER 10001
EXPOSE 8080
# tini forwards SIGTERM to the publisher, which shuts down cleanly
ENTRYPOINT ["/usr/bin/tini", "--", "pragma-validator"]
CMD ["run", "-c", "/config/validator-publisher.yaml"]
