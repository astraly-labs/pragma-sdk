import asyncio
import time

from typing import List
from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger


logger = get_pragma_sdk_logger()


class DexscreenerFetcher(FetcherInterfaceT):
    """
    Dexscreener fetcher.
    NOTE: Only supports USD for quote currencies for now.

    ⚠⚠ The API is still in beta so we expect breaking changes to happen.
    We will support other quote assets when the API is stable.
    """

    publisher: str
    pairs: List[Pair]

    SOURCE = "DEXSCREENER"
    BASE_URL: str = "https://api.dexscreener.com/latest/dex/search"

    async def fetch(
        self,
        session: ClientSession,
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

        NOTE: The base currency being priced must have either a starknet_address
        or an ethereum_address.
        """
        if pair.quote_currency.id not in (
            "USD",
            "USDPLUS",
        ) or pair.base_currency.id in ("USDC", "USDT"):
            return PublisherFetchError(f"No data found for {pair} from Dexscreener")
        if (pair.base_currency.ethereum_address == 0) and (
            pair.base_currency.starknet_address == 0
        ):
            return PublisherFetchError(
                f"No on-chain address for {pair.base_currency.id}, "
                "can't fetch from Dexscreener"
            )
        return await self._fetch_dexscreener_price(pair, session)

    async def _fetch_dexscreener_price(
        self,
        pair: Pair,
        session: ClientSession,
    ) -> SpotEntry | PublisherFetchError:
        """
        Query the dexscreener API and construct the SpotEntry.
        Returns the median price from all available pairs and the total volume.
        """
        pairs_data = await self._query_dexscreener(
            pair,
            session,
        )
        if isinstance(pairs_data, PublisherFetchError):
            return PublisherFetchError(f"No data found for {pair} from Dexscreener")

        pair_data = pairs_data[0]
        price = float(pair_data["priceUsd"])
        volume = float(pair_data["volume"]["h24"])

        return self._construct(
            pair=pair,
            result=price,
            volume=volume,
        )

    async def _query_dexscreener(
        self,
        pair: Pair,
        session: ClientSession,
    ) -> List[dict] | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Dexscreener"
                )
            if resp.status == 200:
                response = await resp.json()
                # NOTE: Response are sorted by highest liq, so we take the first.
                if response["pairs"] is not None and len(response["pairs"]) > 0:
                    return response["pairs"]  # type: ignore[no-any-return]
        return PublisherFetchError(f"No data found for {pair.id} from Dexscreener")

    def format_url(  # type: ignore[override]
        self,
        pair: Pair,
    ) -> str:
        """
        Format the URL to fetch in order to retrieve the price for a pair.
        """
        return f"{self.BASE_URL}?q={pair.base_currency.id.upper()}/USDC"

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
