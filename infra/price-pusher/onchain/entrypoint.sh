#!/bin/bash
set -euo pipefail

exec /opt/price-pusher/.venv/bin/python3.12 price_pusher/main.py ${ARGS}