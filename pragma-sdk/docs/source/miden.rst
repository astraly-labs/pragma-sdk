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

Run this once per environment. It creates your Miden publisher account on-chain and writes credentials locally.

.. code-block:: python

    import asyncio
    from pragma_sdk.miden.client import PragmaMidenClient

    async def main():
        client = PragmaMidenClient(
            network="testnet",
            oracle_id="0xafebd403be621e005bf03b9fec7fe8",  # see pragma-miden README for latest
        )
        await client.initialize()
        print(f"Publisher ID: {client.publisher_id}")

    asyncio.run(main())

This creates three files in your working directory:

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
        results = await client.publish_entries([
            MidenEntry(pair="1:0", price=68199_000000, decimals=6),  # BTC/USD
            MidenEntry(pair="2:0", price=2150_000000,  decimals=6),  # ETH/USD
        ])
        print(results)  # [True, True]

    asyncio.run(main())

Prices use **6 decimal places** — multiply the USD value by ``1_000_000``.

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
      --miden-network testnet

Miden publishing hooks into the existing loop automatically. After each successful Starknet push,
the same entries are forwarded to Miden in a fire-and-forget task — no extra configuration needed.

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
            network: str = "testnet",        # "testnet" | "devnet" | "local"
            oracle_id: str | None = None,    # read from pragma_miden.json if omitted
            storage_path: str | None = None, # CWD by default
            keystore_path: str | None = None,
        ): ...

        async def initialize(self) -> None: ...
        async def publish_entries(self, entries: list[MidenEntry]) -> list[bool]: ...
        async def get_entry(self, pair: str) -> str | None: ...
        async def sync(self) -> None: ...

    class MidenEntry:
        pair: str       # Miden faucet_id, e.g. "1:0"
        price: int      # integer scaled by 10**decimals
        decimals: int
        timestamp: int  # unix timestamp, defaults to now

        @classmethod
        def from_starknet_entry(cls, entry) -> MidenEntry | None:
            """Convert a Starknet Entry. Returns None if the pair is not supported on Miden."""
