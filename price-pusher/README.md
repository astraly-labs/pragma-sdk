# Price pusher


## Usage

The price-pusher service is run through the ClI, to have more information you can use the `--help` command:

```bash
.venv ❯ python price_pusher/main.py --help

Usage: main.py [OPTIONS]
Options:

  -c, --config-file PATH          Path to YAML configuration file.  [required]

  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Logging level.

  -n, --network [sepolia|mainnet]
                                  At which network the price corresponds.
                                  [required]

  -p, --private-key TEXT          Private key of the signer. Format:
                                  aws:secret_name,
                                  plain:private_key,
                                  env:ENV_VAR_NAME,
                                  or keystore:PATH/TO/THE/KEYSTORE:PASSWORD
                                  [required]

  --publisher-name TEXT           Your publisher name.  [required]

  --publisher-address TEXT        Your publisher address.  [required]

  --rpc-url TEXT                  RPC url used to interact with the chain.

  --max-fee INTEGER               Max fee used when using the onchain client.

  --pagination INTEGER            Number of elements per page returned from
                                  the onchain client.

  --enable-strk-fees BOOLEAN      Pay fees using STRK for on chain queries.

  --poller-refresh-interval INTEGER
                                  Interval in seconds between poller
                                  refreshes. Default to 5 seconds.

  --health-port INTEGER           Port for health check HTTP server. Default
                                  to 8080. Set to 0 to disable.

  --max-seconds-without-push INTEGER
                                  Maximum seconds without push before
                                  unhealthy. Default to 300 seconds (5
                                  minutes).

  --evm-rpc-url TEXT              Ethereum RPC URL used by on-chain fetchers
                                  (can be passed multiple times)

  --help                          Show this message and exit
```

For example, to push prices on mainnet with a plain private key:

```sh
uv run price_pusher \
  -c ./config/config.example.yaml \
  --log-level DEBUG \
  -n mainnet \
  -p plain:$PUBLISHER_PV_KEY \
  --publisher-name $PUBLISHER_NAME \
  --publisher-address $PUBLISHER_ADDRESS \
  --rpc-url https://starknet-mainnet.example \
  --evm-rpc-url https://my.ethereum.node
```

### Docker

The published Docker image exposes the CLI directly. You can pass any option (including multiple `--evm-rpc-url` values) when starting the container:

```sh
docker run --rm \
  -v $(pwd)/config.yaml:/opt/price-pusher/config/config.yaml \
  ghcr.io/pragma-labs/price-pusher:latest \
  --config-file /opt/price-pusher/config/config.yaml \
  --network mainnet \
  --private-key plain:$PUBLISHER_PV_KEY \
  --publisher-name $PUBLISHER_NAME \
  --publisher-address $PUBLISHER_ADDRESS \
  --evm-rpc-url https://my.ethereum.node \
  --evm-rpc-url https://backup.rpc.example
```

If you omit `--evm-rpc-url`, the fetchers automatically fall back to the default public Ethereum RPC list bundled with the SDK.

## Architecture

![Architecture Diagram](diagram.png)

(Not 100% up to date and accurate with the latest changes, but the overall view is correct).
