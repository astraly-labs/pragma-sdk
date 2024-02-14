# Contributing

## Setup

1. Clone the `pragma-sdk` repository:
```shell
git clone git@github.com:astraly-labs/pragma-sdk.git
```
2. Install dependencies with Poetry:
```shell
poetry install
```

## Running Tests Locally

1. Install katana
```shell
curl -L https://install.dojoengine.org | bash
source /Users/<user>/.zshenv
dojoup
```

2. Now, you can run tests:
```shell
coverage run -m pytest --net=devnet --client=full_node -v --reruns 5 --only-rerun aiohttp.client_exceptions.ClientConnectorError pragma/tests
```

## Updating ABIs

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
