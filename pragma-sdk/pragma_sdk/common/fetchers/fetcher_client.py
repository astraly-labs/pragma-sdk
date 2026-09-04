import asyncio
import time
from typing import List
import logging

import aiohttp

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.utils import add_sync_methods, felt_to_str
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.exceptions import PublisherFetchError

logger = logging.getLogger(__name__)


@add_sync_methods
class FetcherClient:
    """
    This client extends the pragma client with functionality for fetching from our third party sources.
    It can be used to synchronously or asynchronously fetch assets.

    The client works by setting up fetchers that are provided the assets to fetch and the publisher name.

    Example usage:

    .. code-block:: python

        pairs = [
            Pair.from_tickers("BTC", "USD"),
            Pair.from_tickers("ETH", "USD"),
        ]

        bitstamp_fetcher = BitstampFetcher(pairs, "publisher_test")
        gateio_fetcher = GateIOFetcher(pairs, "publisher_test")

        fetchers = [
            bitstamp_fetcher,
            gateio_fetcher,
        ]

        fc = FetcherClient()
        fc.add_fetchers(fetchers)

        await fc.fetch()
        fc.fetch_sync()

    You can also set a custom timeout duration as followed:

    .. code-block:: python

        await fc.fetch(timeout_duration=20)  # Denominated in seconds
    """

    __fetchers: List[FetcherInterfaceT] = []

    @property
    def fetchers(self) -> List[FetcherInterfaceT]:
        return self.__fetchers

    @fetchers.setter
    def fetchers(self, value: List[FetcherInterfaceT]) -> None:
        if len(value) > 0:
            self.__fetchers = value
        else:
            raise ValueError("Fetcher list cannot be empty")

    def add_fetchers(self, fetchers: List[FetcherInterfaceT]) -> None:
        """
        Add fetchers to the supported fetchers list.
        """
        self.fetchers.extend(fetchers)

    def add_fetcher(self, fetcher: FetcherInterfaceT) -> None:
        """
        Add a single fetcher to the supported fetchers list.
        """
        self.fetchers.append(fetcher)

    @staticmethod
    def _reject_zero_price(value: Entry | BaseException) -> Entry | BaseException:
        """
        A dead market (Binance DAIUSDT, Bitstamp strkusd, ...) still answers a
        well-formed ticker at 0. Zero is never a price: it would drag every
        median it lands in. Convert it to an error before it reaches a publisher.
        """
        price = getattr(value, "price", None)
        if isinstance(price, (int, float)) and price <= 0:
            source = felt_to_str(getattr(getattr(value, "base", None), "source", 0))
            pair_id = felt_to_str(getattr(value, "pair_id", 0))
            logger.warning(
                "[⚠️ Fetcher] Rejecting non-positive price %s for %s from %s",
                price,
                pair_id,
                source,
            )
            return PublisherFetchError(
                f"Non-positive price {price} for {pair_id} from {source}"
            )
        return value

    async def fetch(
        self,
        filter_exceptions: bool = True,
        return_exceptions: bool = True,
        timeout_duration: int = 20,
    ) -> List[Entry | PublisherFetchError | Exception]:
        """
        Fetch data from all fetchers asynchronously.
        Fetching is done in parallel for all fetchers.

        :param filter_exceptions: If True, filters out exceptions from the result list
        :param return_exceptions: If True, returns exceptions in the result list
        :param timeout_duration: Timeout duration for each fetcher
        :return: List of fetched data
        """
        start_time = time.time()  # noqa: F841
        tasks = []

        # Create a timeout for both connection and individual operations
        timeout = aiohttp.ClientTimeout(
            total=None,  # No timeout for the entire session
            connect=timeout_duration,
            sock_read=timeout_duration,
            sock_connect=timeout_duration,
        )

        async with aiohttp.ClientSession(
            timeout=timeout, connector=aiohttp.TCPConnector(limit=0)
        ) as session:
            tasks = []
            for idx, fetcher in enumerate(self.fetchers):

                async def wrapped_fetch(f, i):
                    try:
                        # Add timeout to the individual fetch operation
                        async with asyncio.timeout(timeout_duration):
                            fetch_start = time.time()
                            result = await f.fetch(session)
                            fetch_time = time.time() - fetch_start
                            logger.debug(
                                f"Fetcher {i} ({f.__class__.__name__}) completed in {fetch_time:.2f}s"
                            )
                            return result
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Fetcher {i} ({f.__class__.__name__}) timed out after {timeout_duration}s"
                        )
                        return PublisherFetchError(f"Timeout after {timeout_duration}s")
                    except Exception as e:
                        logger.error(
                            f"Fetcher {i} ({f.__class__.__name__}) failed: {str(e)}"
                        )
                        raise

                tasks.append(wrapped_fetch(fetcher, idx))

            gather_start = time.time()
            result = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
            logger.info(f"Gathered all results in {time.time() - gather_start:.2f}s")

            result = [r if isinstance(r, list) else [r] for r in result]
            result = [val for subl in result for val in subl]  # flatten
            result = [self._reject_zero_price(val) for val in result]

            if filter_exceptions:
                result = [
                    subl for subl in result if not isinstance(subl, BaseException)
                ]
            return result

        await asyncio.sleep(0)  # Graceful shutdown
