FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=off PIP_DISABLE_PIP_VERSION_CHECK=on PIP_DEFAULT_TIMEOUT=100

ENV PATH="/root/.local/bin:${PATH}"

FROM base as builder

RUN apt-get update && apt-get install --no-install-recommends -y gcc libgmp3-dev pipx

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY pragma-utils/ /opt/pragma-utils/
COPY price-pusher/ /opt/price-pusher/
WORKDIR /opt/price-pusher
RUN uv sync --all-extras

FROM base as final
COPY --from=builder /opt /opt
COPY infra/price-pusher/config/ /opt/price-pusher/config/
WORKDIR /opt/price-pusher
ENTRYPOINT /opt/price-pusher/.venv/bin/python3.12 price_pusher/main.py -c ${CONFIG_PATH} -t ${TARGET} -n ${NETWORK} -p ${PRIVATE_KEY} --publisher-name ${PUBLISHER_NAME} --publisher-address ${PUBLISHER_ADDRESS} --api-key ${API_KEY} --api-base-url ${API_BASE_URL}
