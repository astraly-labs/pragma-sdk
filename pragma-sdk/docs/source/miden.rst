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
            MidenEntry(pair="1:0", price=6819900000000, decimals=8),  # BTC/USD
            MidenEntry(pair="2:0", price=215000000000,  decimals=8),  # ETH/USD
        ])
        print(results)  # [True, True]

    asyncio.run(main())

When converting from a Pragma Starknet ``Entry`` via ``MidenEntry.from_starknet_entry``,
the decimals are derived from the pair's currencies (``min(base.decimals, quote.decimals)``,
which is **8** for all currently supported pairs). Don't hardcode 6 in new callers.

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

Supported pairs
---------------

Only pairs in the following mapping are published to Miden. Unsupported pairs are silently skipped.

.. list-table::
   :header-rows: 1
   :widths: 20 20

   * - Starknet pair_id
     - Miden faucet_id
   * - ``BTC/USD``
     - ``1:0``
   * - ``ETH/USD``
     - ``2:0``
   * - ``SOL/USD``
     - ``3:0``
   * - ``BNB/USD``
     - ``4:0``
   * - ``XRP/USD``
     - ``5:0``
   * - ``HYPE/USD``
     - ``6:0``
   * - ``POL/USD``
     - ``7:0``

To add a new pair, update ``STARKNET_PAIR_TO_MIDEN_FAUCET`` in ``pragma_sdk/miden/client.py`` and bump the ``pragma-sdk`` version.

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
        pair: str       # Miden faucet_id, e.g. "1:0"
        price: int      # integer scaled by 10**decimals
        decimals: int
        timestamp: int  # unix timestamp, defaults to now

        @classmethod
        def from_starknet_entry(cls, entry) -> MidenEntry | None:
            """Convert a Starknet Entry. Returns None if the pair is unsupported on Miden
            or if the pair's decimals cannot be resolved."""
