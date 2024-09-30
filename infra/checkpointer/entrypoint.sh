#!/bin/bash
set -euo pipefail
export INFISICAL_TOKEN=$(infisical login --method=universal-auth --client-id=${INFISCAL_CLIENT_ID} --client-secret=${INFISICAL_CLIENT_SECRET} --silent --plain)
infisical export  --projectId=${INFISCAL_PROJECT_ID} --env=${INFISCAL_ENV}  --path=${INFISCAL_APP_PATH} > .env
source .env
exec /opt/checkpointer/.venv/bin/python3.12 checkpointer/main.py -c ${CONFIG_PATH} -n ${NETWORK} --oracle-address ${ORACLE_ADDRESS} --admin-address ${ADMIN_ADDRESS} --private-key ${PRIVATE_KEY} -t ${CHECK_INTERVAL} --rpc-url ${RPC_URL}