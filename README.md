# Pragma SDK

[![codecov](https://codecov.io/gh/Astraly-Labs/pragma-sdk/graph/badge.svg?token=98pUFYGHIK)](https://codecov.io/gh/Astraly-Labs/pragma-sdk)

[![Tests](https://github.com/Astraly-Labs/pragma-sdk/actions/workflows/tests.yml/badge.svg)](https://github.com/Astraly-Labs/pragma-sdk/actions/workflows/tests.yml)

[![Package](https://img.shields.io/pypi/v/pragma-sdk)](https://pypi.org/project/pragma-sdk/)

[![Read the Docs](https://img.shields.io/readthedocs/pragma-docs)](https://pragma-docs.readthedocs.io/en/latest/index.html)

---

**Pragma SDK, written in Python.**

One can leverage this SDK to interact with Pragma on Starknet.
This SDK should also be used by Data Providers willing to push data on Pragma contracts.

## About

For more information, see the [project's repository](https://github.com/Astraly-Labs/Pragma), [documentation overview](https://docs.pragma.build/) and [documentation on how to publish data](https://docs.pragma.build/Resources/Cairo%201/data-feeds/publishing-data).

## Repository Structure

Our main SDK:

- <a href="./pragma-sdk">Python SDK</a>

Our utility library:

- <a href="./pragma-utils">Pragma utils</a>

Our services used to publish data etc...:

- <a href="./price-pusher">Price Pusher</a>
- <a href="./vrf-listener">VRF Listener</a>
- <a href="./checkpointer">Checkpointer</a>
- <a href="./merkle-maker">Merkle Maker</a>

## Releasing a new version

We provide a version management script to help maintain consistent versioning across all packages.

### Installation

1. Make the script executable:

```bash
chmod +x scripts/version.sh
```

### Usage

Run the version checker:

```bash
bash scripts/version.sh
```

The script will:

- Fetch the latest version from PyPI
- Check all local package versions
- Display the current version status

- Offer options to:

```bash
Bump the major version (x.y.z → x+1.0.0)
Bump the minor version (x.y.z → x.y+1.0)
Bump the patch version (x.y.z → x.y.z+1)
```

The script will automatically update all `__init__.py` files in the following packages:

```sh
.
    └── pragma-sdk
        ├── pragma-sdk
        ├── pragma-utils
        ├── merkle-maker
        ├── price-pusher
        ├── vrf-listener
        └── lp-pricer
```

> **Note**: Make sure to commit and push the version changes after running the script.

## Contributing

See the [CONTRIBUTING](./CONTRIBUTING.md) guide.
