Miden Publishing
================

Pragma SDK supports optional publishing to the `Pragma Miden oracle <https://docs.pragma.build/pragma/miden/introduction>`_
alongside Starknet. Miden publishing is completely isolated — a failure on Miden never affects the Starknet loop.

Installation
------------

Miden support is an optional dependency. Install it with:

.. code-block:: bash

    pip install pragma-sdk[miden]

This installs ``pm-publisher``, the Rust-backed wheel that handles Miden account management and transaction submission.

Initialize your publisher account
----------------------------------

Run this **once per environment** to create your Miden publisher account on-chain.
``initialize()`` is idempotent: if a ``pragma_miden.json`` already exists for the network,
it is reused. Otherwise a fresh on-chain account is created.

Get the latest ``oracle_id`` for your target network from
`pragma_miden.json in the pragma-miden repo <https://github.com/astraly-labs/pragma-miden/blob/main/pragma_miden.json>`_.

.. code-block:: python

    import asyncio
    from pragma_sdk.miden.client import PragmaMidenClient

    async def main():
        client = PragmaMidenClient(
            network="testnet",
            oracle_id="<latest-oracle-id-from-pragma_miden.json>",
        )
        await client.initialize()
        print(f"Publisher ID: {client.publisher_id}")

    asyncio.run(main())

The first init creates three artifacts (locations are configurable):

- ``pragma_miden.json`` — your publisher ID and oracle address
- ``keystore/`` — account signing keys (**back this up**)
- ``miden_storage/store.sqlite3`` — local chain state

Once initialized, share your publisher ID with the Pragma team to get registered on the oracle.

Publish prices
--------------

After initialization, publish entries directly:

.. code-block:: python

    import asyncio
    from pragma_sdk.miden.client import PragmaMidenClient, MidenEntry

    async def main():
        client = PragmaMidenClient(network="testnet")
        await client.initialize()  # reuses existing config if present
        results = await client.publish_entries([
            MidenEntry(pair="BTC/USD", price=6819900000000, decimals=8),
            MidenEntry(pair="ETH/USD", price=215000000000,  decimals=8),
        ])
        print(results)  # [True, True]

    asyncio.run(main())

When converting from a Pragma Starknet ``Entry`` via ``MidenEntry.from_starknet_entry``,
the decimals are derived from the pair's currencies (``min(base.decimals, quote.decimals)``,
which is **8** for most pairs but **6** for ``USDT/USD``, ``USDC/USD`` and ``XAUT/USD``). Don't hardcode it in new callers.

Integrate with the price-pusher
--------------------------------

If you run the ``price-pusher``, pass ``--miden-network`` to enable Miden publishing alongside Starknet:

.. code-block:: bash

    price-pusher \
      --config-file config.yaml \
      --network mainnet \
      --private-key plain:0x... \
      --publisher-name MY_PUBLISHER \
      --publisher-address 0x... \
      --miden-network testnet \
      --miden-config-path /path/to/pragma_miden.json \
      --miden-storage-path /path/to/miden_storage \
      --miden-keystore-path /path/to/keystore

The Miden client is initialized **once at startup** (out of the hot Starknet loop). If init
fails — network down, missing config, etc. — Miden is silently disabled and Starknet keeps
running. After each successful Starknet push, supported pairs are forwarded to Miden in a
thread-offloaded fire-and-forget task with per-call timeouts, so a stuck Miden node cannot
freeze the Starknet pusher.

The ``--miden-config-path`` / ``--miden-storage-path`` / ``--miden-keystore-path`` flags
are optional — if omitted, paths are resolved relative to the pusher's working directory.

Miden only
^^^^^^^^^^

To publish to Miden without a Starknet account, pass ``--miden-only`` instead of the Starknet options
(``--network``, ``--private-key`` and ``--publisher-address`` are then not needed):
there is no Starknet client and no Starknet push, and every configured pair of ``MIDEN_PAIRS`` is
forwarded to Miden, whether its group is flagged ``miden_only`` or not.

.. code-block:: bash

    price-pusher \
      --config-file config.yaml \
      --publisher-name MY_PUBLISHER \
      --miden-only \
      --miden-network testnet \
      --miden-config-path /path/to/pragma_miden.json \
      --miden-storage-path /path/to/miden_storage \
      --miden-keystore-path /path/to/keystore

Supported pairs
---------------

Only the pairs of ``MIDEN_PAIRS`` (``pragma_sdk/miden/client.py``) are published to Miden. Unsupported pairs
are silently skipped. A pair is identified on chain by its name: the oracle derives the storage key from
``BASE/QUOTE`` (``pm_publisher.pair_key("BTC/USD")``), so there is no index to register or keep stable.

``BTC/USD`` (8 decimals), ``ETH/USD`` (8), ``WBTC/USD`` (8), ``USDT/USD`` (6), ``DAI/USD`` (8), ``ZEC/USD`` (8),
``XMR/USD`` (8), ``DASH/USD`` (8), ``XAUT/USD`` (6), ``PAXG/USD`` (8), ``LINK/USD`` (8), ``UNI/USD`` (8),
``AAVE/USD`` (8), ``MORPHO/USD`` (8), ``USDC/USD`` (6).

Miden-only feeds
^^^^^^^^^^^^^^^^

A price-pusher config group flagged ``miden_only: true`` is polled by the fetchers and
forwarded to Miden, but no Starknet listener is created for it, so its pairs are never
pushed to Starknet. ``ZEC/USD`` to ``MORPHO/USD`` above are published this way (``USDC/USD`` is a regular pair that is pushed to both chains):

.. code-block:: yaml

    - pairs:
        spot:
          - ZEC/USD
          - XAUT/USD
      time_difference: 1800
      price_deviation: 0.01
      miden_only: true

To add a new pair, add it to ``MIDEN_PAIRS`` in ``pragma_sdk/miden/client.py`` and bump the ``pragma-sdk`` version.

API reference
-------------

.. code-block:: python

    class PragmaMidenClient:
        def __init__(
            self,
            network: str = "testnet",         # "testnet" | "devnet" | "local"
            oracle_id: str | None = None,     # read from pragma_miden.json if omitted
            storage_path: str | None = None,
            keystore_path: str | None = None,
            config_path: str | Path | None = None,  # path to pragma_miden.json
        ): ...

        async def initialize(self) -> None: ...                                 # idempotent
        async def publish_entries(self, entries: list[MidenEntry]) -> list[bool]: ...
        async def get_entry(self, pair: str) -> str | None: ...                 # None on failure
        async def sync(self) -> None: ...

    class MidenEntry:
        pair: str       # pair name, e.g. "BTC/USD"
        price: int      # integer scaled by 10**decimals
        decimals: int
        timestamp: int  # unix timestamp, defaults to now

        @classmethod
        def from_starknet_entry(cls, entry) -> MidenEntry | None:
            """Convert a Starknet Entry. Returns None if the pair is unsupported on Miden
            or if the pair's decimals cannot be resolved."""
