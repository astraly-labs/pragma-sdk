Quickstart
==========

This is a quickstart guide to get you up and running with the Pragma SDK.

Fetch data
---------------

To fetch data on 3rd parties API, one can use the `FetcherClient<pragma_sdk.common.fetchers>`.

Here is step by step example:

.. code-block:: python

    from pragma_sdk.common.fetchers import FetcherClient
    from pragma_sdk.common.fetchers.fetchers import BitstampFetcher, GateIOFetcher

    # 1. Create a list of pairs that you want to fetch
    pairs = [
        Pair.from_tickers("BTC","USD"),
        Pair.from_tickers("ETH","USD"),
    ]

    # 2. Create your fetchers and add them to the FetcherClient
    bitstamp_fetcher = BitstampFetcher(pairs, "publisher_test")
    gateio_fetcher = GateIOFetcher(pairs, "publisher_test")
    fetchers = [
        bitstamp_fetcher,
        gateio_fetcher,
    ]

    fc = FetcherClient()
    fc.add_fetchers(fetchers)

    # 3. Fetch the data
    entries = await fc.fetch()

.. hint::

    If you are experiencing issues with fetching, it's most likely due to the fetcher not being able to connect to the API.
    Some fetchers do require ``api_key`` keyword argument in their constructor. 
    Please refer to the fetcher's documentation for more information.
    Also if you want to fetch data synchronously, you can use the :meth:`fetch_sync` method.
