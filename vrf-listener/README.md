# VRF Listener

Service used to listen for VRF requests and handle them.

## Usage

The service is ran through the CLI, to have more information you can use the `--help` command:

```bash
.venv ❯ python vrf_listener/main.py --help

Usage: main.py [OPTIONS]

    VRF Listener entry point.

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -n, --network [sepolia|mainnet]
                                  Which network to listen. Defaults to
                                  SEPOLIA.  [required]

  --rpc-url TEXT                  RPC url used by the onchain client.

  --vrf-address TEXT              Address of the VRF contract  [required]

  --admin-address TEXT            Address of the Admin contract  [required]

  -p, --private-key TEXT          Private key of the signer. Format:
                                  aws:secret_name, plain:private_key, or
                                  env:ENV_VAR_NAME  [required]

  -t, --check-requests-interval INTEGER RANGE
                                  Delay in seconds between checks for VRF
                                  requests. Defaults to 10 seconds.  [x>=0]

  --ignore-request-threshold INTEGER RANGE
                                  Blocks to ignore before the current block
                                  for the handling.  [x>=0]

  --index-with-apibara            Self index the VRF requests using Apibara
                                  instead of using Starknet.py

  --apibara-api-key TEXT          Apibara API key. Needed when indexing with
                                  Apibara.

  -w, --whitelisted HEX_STRING    List of whitelisted addresses for which we
                                  won't check their fees and pay for them if
                                  needed.
  --help                          Show this message and exit.
```

For example:

```sh
poetry run vrf_listener --vrf-address $PRAGMA_VRF_CONTRACT --admin-address $PRAGMA_ORACLE_ADMIN --private-key plain:$PRAGMA_ADMIN_PV_KEY -w $ADDR_1 -w $ADDR_2 # ...
```

Will start listening for VRF requests on Sepolia every 10 seconds since block 0.
