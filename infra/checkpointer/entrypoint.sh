#!/bin/bash
set -euo pipefail

# Validate required environment variables
required_vars=(
    "CONFIG_PATH"
    "NETWORK"
    "ORACLE_ADDRESS"
    "ADMIN_ADDRESS"
    "PRIVATE_KEY"
    "CHECK_INTERVAL"
    "RPC_URL"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "Error: Required environment variable $var is not set"
        exit 1
    fi
done

exec /opt/checkpointer/.venv/bin/python3.12 checkpointer/main.py \
    -c ${CONFIG_PATH} \
    -n ${NETWORK} \
    --oracle-address ${ORACLE_ADDRESS} \
    --admin-address ${ADMIN_ADDRESS} \
    --private-key ${PRIVATE_KEY} \
    -t ${CHECK_INTERVAL} \
    --rpc-url ${RPC_URL}
