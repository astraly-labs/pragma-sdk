#!/bin/bash
set -euox pipefail
export INFISICAL_TOKEN=$(infisical login --method=universal-auth --client-id=${INFISICAL_CLIENT_ID} --client-secret=${INFISICAL_CLIENT_SECRET} --silent --plain)
infisical export  --projectId=${INFISICAL_PROJECT_ID} --env=${INFISICAL_ENV}  --path=${INFISICAL_APP_PATH} > .env
source .env
exec /opt/checkpointer/.venv/bin/python3.12 checkpointer/main.py -c ${CONFIG_PATH} -n ${NETWORK} --oracle-address ${ORACLE_ADDRESS} --admin-address ${ADMIN_ADDRESS} --private-key ${PRIVATE_KEY} -t ${CHECK_INTERVAL} --rpc-url ${RPC_URL}