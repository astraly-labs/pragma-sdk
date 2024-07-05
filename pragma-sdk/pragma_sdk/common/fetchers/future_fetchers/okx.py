import json
import logging
from typing import List

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import FutureEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class OkxFutureFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://okx.com/api/v5/market/tickers"
    SOURCE: str = "OKX"
    TIMESTAMP_URL: str = "https://www.okx.com/api/v5/public/instruments"

    async def fetch_expiry_timestamp(self, pair: Pair, instrument_id, session):
        url = self.format_expiry_timestamp_url(instrument_id)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from OKX")
            result = await resp.json(content_type="application/json")
            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from OKX")
            return result["data"][0]["expTime"]

    def format_expiry_timestamp_url(self, instrument_id):
        return f"{self.TIMESTAMP_URL}?instType=FUTURES&instId={instrument_id}"

    async def fetch_pair(self, pair: Pair, session: ClientSession):
        url = self.format_url(pair)
        future_entries = []
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from OKX")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"OKX: Unexpected content type: {content_type}")

            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from OKX")
            result_len = len(result["data"])
            if result_len > 1:
                for i in range(0, result_len):
                    expiry_timestamp = await self.fetch_expiry_timestamp(
                        pair, result["data"][i]["instId"], session
                    )
                    future_entries.append(
                        self._construct(pair, result["data"][i], expiry_timestamp)
                    )
            return future_entries

    async def fetch(
        self, session: ClientSession
    ) -> List[FutureEntry | PublisherFetchError]:
        entries = []
        for pair in self.pairs:
            future_entries = await self.fetch_pair(pair, session)
            if isinstance(future_entries, list):
                entries.extend(future_entries)
            else:
                entries.append(future_entries)
        return entries

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}?instType=FUTURES&uly={pair.base_currency.id}-{pair.quote_currency.id}"
        return url

    def _construct(self, pair: Pair, data, expiry_timestamp) -> List[FutureEntry]:
        timestamp = int(int(data["ts"]) / 1000)
        decimals = pair.decimals()
        price = float(data["last"])
        price_int = int(price * (10**decimals))
        volume = float(data["volCcy24h"])

        logger.info("Fetched future for %s from OKX", pair.id)

        return FutureEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            expiry_timestamp=int(expiry_timestamp),
        )
