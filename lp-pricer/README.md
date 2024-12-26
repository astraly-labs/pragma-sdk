# Lp Pricer

Service used to price Defi Pools using the `LpFetcher` from the SDK.

### Usage

The service is ran through the CLI, to have more information you can use the `--help` command:

```bash
.venv ❯ uv run lp_pricer --help

Usage: lp_pricer [OPTIONS]

  Lp Pricer entry point.

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -c, --config-file PATH          Path to YAML configuration file.  [required]

  -n, --network [sepolia|mainnet|devnet|pragma_devnet]
                                  On which networks the checkpoints will be
                                  set.  [required]

  --redis-host TEXT               Host where the Redis service is live. Format
                                  is HOST:PORT, example: localhost:6379

  --rpc-url TEXT                  RPC url used by the onchain client.

  --publisher-name TEXT           Name of the publisher of the LP Pricer.
                                  [required]

  --publisher-address TEXT        Address of the publisher of the LP Pricer.
                                  [required]

  -p, --private-key TEXT          Private key of the publisher. Format:
                                  aws:secret_name, plain:private_key,
                                  env:ENV_VAR_NAME, or
                                  keystore:PATH/TO/THE/KEYSTORE:PASSWORD
                                  [required]

  --help                          Show this message and exit.
```

For example:

```sh
uv run lp_pricer -c ./config/config.example.yaml --publisher-name $PUBLISHER_NAME --publisher-address $PUBLISHER_ADDRESS -p plain:$PUBLISHER_PV_KEY
```

Will start storing reserves & supply for the provided pools until there is enough to price them and will push the prices on chain.
