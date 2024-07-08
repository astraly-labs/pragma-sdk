# Contributing

## Setup

1. Clone the `pragma-sdk` repository:
```shell
git clone git@github.com:astraly-labs/pragma-sdk.git
```
2. Install dependencies with Poetry:
```shell
sh scripts/poetry_install.sh
```

It will create a `.venv` virtualenv for each package of our monorepo that you can later activate, for example for the sdk:

```shell
cd pragma-sdk
source .venv/bin/activate
```

## Running Tests Locally

We use [starknet-devnet-rs](https://0xspaceshard.github.io/starknet-devnet-rs/) for our integration tests, you can install it through Rust's package manager, `cargo`.

1. Install Rust
```shell
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

2. Install Starknet-devnet
```shell
cargo install starknet-devnet
```

3. Now, you can run tests, for example in the pragma-sdk repository:
```shell
cd pragma-sdk
source .venv/bin/activate
coverage run -m pytest --net=devnet --client=full_node -v --reruns 5 --only-rerun aiohttp.client_exceptions.ClientConnectorError tests
```

## Updating pragma-oracle ABIs

1. Upgrade submodule
```shell
git submodule update --remote
```

2. Compile contracts
```shell
cd pragma-oracle && scarb build
```

3. Update ABIs
```shell
poe update_abis
```
