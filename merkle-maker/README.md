# Merkle Maker

Service used to publish the latest Merkle Feed onchain and the associated data on Redis.

### Usage

The service is run through the CLI, to have more information you can use the `--help` command:

```bash
.venv ❯ uv run merkle_maker --help

Usage: merkle_maker [OPTIONS]

  Merkle Maker entry point.

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -n, --network [sepolia|mainnet]
                                  On which networks the checkpoints will be
                                  set.  [required]

  --redis-host TEXT               Host where the Redis service is live. Format
                                  is HOST:PORT, example: localhost:6379

  --rpc-url TEXT                  RPC url used by the onchain client.

  --publisher-name TEXT           Name of the publisher of the Merkle Feed.
                                  [required]

  --publisher-address TEXT        Address of the publisher of the Merkle Feed.
                                  [required]

  -p, --private-key TEXT          Private key of the publisher. Format:
                                  aws:secret_name, plain:private_key,
                                  env:ENV_VAR_NAME, or
                                  keystore:PATH/TO/THE/KEYSTORE:PASSWORD
                                  [required]

  -b, --block-interval INTEGER RANGE
                                  Delay in block between each new Merkle Feed
                                  is published.  [x>=1]

  --help                          Show this message and exit.
```

For example:

```sh
uv run merkle_maker --publisher-name $PUBLISHER_NAME --publisher-address $PUBLISHER_ADDRESS -p plain:$PUBLISHER_PV_KEY
```

Will start publishing a new Merkle Feed onchain through a GenericEntry every blocks and store the data used in a Redis database, by default to `localhost:6379`
