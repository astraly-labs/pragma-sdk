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

## Contributing

See the [CONTRIBUTING](./CONTRIBUTING.md) guide.
