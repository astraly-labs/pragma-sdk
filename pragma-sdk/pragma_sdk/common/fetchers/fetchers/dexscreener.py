import asyncio
import time

from typing import List
from aiohttp import ClientSession

from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

from pragma_sdk.onchain.client import PragmaOnChainClient

logger = get_pragma_sdk_logger()


class DexscreenerFetcher(FetcherInterfaceT):
    publisher: str
    pairs: List[Pair]
    _client: PragmaOnChainClient

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDC",
        }
    )
    SOURCE = "DEXSCREENER"
    BASE_URL: str = "https://api.dexscreener.com/latest/dex"

    # NOTE: We only check for starknet for now
    CHAIN_ID = "starknet"

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetch prices from all pairs from Dexscreener.
        """
        entries = []
        for pair in self.pairs:
            entries.append(self.fetch_pair(pair, session))
        return list(await asyncio.gather(*entries, return_exceptions=True))  # type: ignore[call-overload]

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        """
        Fetch the price for a pair and return the SpotEntry.

        NOTE: The currencies of the pair must have a starknet_address.
        """
        pair = self.hop_handler.get_hop_pair(pair) or pair
        if pair.base_currency.starknet_address == 0:
            return PublisherFetchError(
                f"Failed to fetch data for {pair} from Dexscreener: "
                f"{pair.base_currency.id} starknet_address is None."
            )
        if pair.base_currency.starknet_address == 0:
            return PublisherFetchError(
                f"Failed to fetch data for {pair} from Dexscreener: "
                f"{pair.quote_currency.id} starknet_address is None."
            )
        return await self._fetch_dexscreener_price(pair, session)

    async def _fetch_dexscreener_price(
        self,
        pair: Pair,
        session: ClientSession,
    ) -> SpotEntry | PublisherFetchError:
        """
        Query the dexscreener API and construct the SpotEntry.

        NOTE: It is really unclear at the moment how the pair is actually constructed,
        sometimes the quote asset is in front of the base asset...
        To be sure it works, we try both.
        """
        pair_data = await self._query_dexscreener(
            pair.base_currency,
            pair.quote_currency,
            session,
        )

        if isinstance(pair_data, PublisherFetchError):
            pair_data = await self._query_dexscreener(
                pair.quote_currency,
                pair.base_currency,
                session,
            )
            if isinstance(pair_data, PublisherFetchError):
                return PublisherFetchError(f"No data found for {pair} from Dexscreener")

        return self._construct(
            pair=pair,
            result=float(pair_data["priceUsd"]),
            volume=float(pair_data["volume"]["h24"]),
        )

    async def _query_dexscreener(
        self, base: Currency, quote: Currency, session: ClientSession
    ) -> dict | PublisherFetchError:
        pair_id = f"{base.id}/{quote.id}"
        url = self.format_url(hex(base.starknet_address), hex(quote.starknet_address))
        print(url)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair_id} from Dexscreener"
                )
            if resp.status == 200:
                response = await resp.json()
                # NOTE: Response are sorted by highest liq, so we take the first.
                print(response)
                if len(response["pairs"]) > 0:
                    return response["pairs"][0]  # type: ignore[no-any-return]
        return PublisherFetchError(f"No data found for {pair_id} from Dexscreener")

    def format_url(  # type: ignore[override]
        self,
        base_address: str,
        quote_address: str,
    ) -> str:
        """
        Format the URL to fetch in order to retrieve the price for a pair.
        """
        return f"{self.BASE_URL}/search?q={base_address}-{quote_address}"

    def _construct(self, pair: Pair, result: float, volume: float) -> SpotEntry:
        price_int = int(result * (10 ** pair.decimals()))
        logger.debug("Fetched price %d for %s from Dexscreener", price_int, pair)
        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=0,
        )


from pragma_sdk.common.fetchers.fetcher_client import FetcherClient


async def main():
    pairs = [Pair.from_tickers("EKUBO", "USDC")]
    fc = FetcherClient()

    dex = DexscreenerFetcher(pairs, "AKHERCHA")
    fc.add_fetcher(dex)

    entries = await fc.fetch(filter_exceptions=False)
    print(entries)


if __name__ == "__main__":
    asyncio.run(main())
