#!/bin/bash

set -euo pipefail

# Execute Stunnel
/usr/bin/stunnel stunnel.conf &

sleep 5

# Execute LMAX Connector
exec /opt/lmax-connector/.venv/bin/python3.12 -m lmax_connector
