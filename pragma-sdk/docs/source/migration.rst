Migration
==========

This is a migration guide from the Pragma SDK v1.x.x to v2.x.x.

If you want the full changelog please refer to our official `Github release <https://github.com/astraly-labs/pragma-sdk/releases/tag/v2.0.0-rc0>`_.

Also please refer to our updated `publishing guide <https://docs.pragma.build/Resources/Cairo%201/data-feeds/publishing-data>`_ if you are a data provider.

The main changes are :

.. important::

    Keystores are now supported in the SDK and it is highly recommended to use them as plain private keys are unsafe.
    The `Keystore` type has been introduced which is a tuple with the following fields:

    - `path`: The path to the keystore file.
    - `password`: The password to unlock the keystore file.

    To use a keystore, you can pass it as an argument to the `PragmaOnChainClient` constructor.

    .. code-block:: python

        from pragma_sdk.onchain.client import PragmaOnChainClient

        publisher_client = PragmaOnChainClient(
            account_private_key=("/path/to/keystore", keystore_password),
            account_contract_address=publisher_address,
            network="https://my.custom.mainnet.rpc.url",
            chain_name="mainnet"
        )


- The type `PragmaAsset` does not exist anymore. Now the main type is the `Pair` type.
- There is no more global variable `PRAGMA_ALL_ASSETS`, you should create yourself the list of pairs you want to publish.

.. code-block:: python

    from pragma_sdk.common.types.pair import Pair

    pairs = [
        Pair.from_tickers("BTC","USD"),
        Pair.from_tickers("ETH","USD"),
    ]

- You do not need to use the `currency_pair_to_pair_id(*asset["pair"])` utils, now simply use `pair.id`
- To get the decimals of the pair just use `pair.decimals()`
- There is no more `PragmaPublisherClient` now you should use the `PragmaOnChainClient` to publish data on-chain.
- To publish data on the Pragma API, you should use the `PragmaAPIClient` class.
- To fetch data from external APIs, you should now use the `PragmaFetcherClient` class.
- Volume autoscaling has been removed, now you should provide the volume in the correct unit (24h cumulative volume in base asset).

.. danger::

    There is no more `testnet` network, now you should use `sepolia` for the testnet.

- If you want to pay your gas fees in `STRK` you can enable it in the `execution_config` constructor argument.

.. code-block:: python

    from pragma_sdk.onchain.types.execution_config import ExecutionConfig
    from pragma_sdk.onchain.client import PragmaOnChainClient

    publisher_client = PragmaOnChainClient(
        account_private_key=("/path/to/keystore", keystore_password),
        account_contract_address=publisher_address,
        network="https://my.custom.mainnet.rpc.url",
        chain_name="mainnet",
        execution_config=ExecutionConfig(enable_strk_fees=True)
    )
