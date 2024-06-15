import json
import logging
from datetime import datetime, timezone
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaFutureAsset
from pragma.core.entry import FutureEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class BinanceFutureFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://fapi.binance.com/fapi/v1/premiumIndex"
    VOLUME_URL: str = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    SOURCE: str = "BINANCE"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_volume(self, asset, session):
        pair = asset["pair"]
        url = f"{self.VOLUME_URL}"
        selection = f"{pair[0]}{pair[1]}"
        volume_arr = []
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance"
                )
            result = await resp.json(content_type="application/json")
            for element in result:
                if selection in element["symbol"]:
                    volume_arr.append((element["symbol"], element["quoteVolume"]))
            return volume_arr

    async def fetch_pair(
        self, asset: PragmaFutureAsset, session: ClientSession
    ) -> Union[FutureEntry, PublisherFetchError]:
        pair = asset["pair"]
        filtered_data = []
        url = f"{self.BASE_URL}"
        selection = f"{pair[0]}{pair[1]}"
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"Binance: Unexpected content type: {content_type}")

            for element in result:
                if selection in element["symbol"]:
                    filtered_data.append(element)
            volume_arr = await self.fetch_volume(asset, session)
            return self._construct(asset, filtered_data, volume_arr)

    async def fetch(self, session: ClientSession):
        entries = []
        for asset in self.assets:
            if asset["type"] != "FUTURE":
                logger.debug("Skipping Binance for non-future asset %s", asset)
                continue
            future_entries = await self.fetch_pair(asset, session)
            if isinstance(future_entries, list):
                entries.extend(future_entries)
            else:
                entries.append(future_entries)
        return entries

    def format_url(self, quote_asset, base_asset):
        return self.BASE_URL

    def retrieve_volume(self, asset, volume_arr):
        for list_asset, list_vol in volume_arr:
            if asset == list_asset:
                return list_vol
        return 0

    def _construct(self, asset, result, volume_arr) -> List[FutureEntry]:
        pair = asset["pair"]
        result_arr = []
        for data in result:
            timestamp = int(data["time"])
            price = float(data["markPrice"])
            price_int = int(price * (10 ** asset["decimals"]))
            pair_id = currency_pair_to_pair_id(*pair)
            volume = float(self.retrieve_volume(data["symbol"], volume_arr)) / (
                10 ** asset["decimals"]
            )
            if data["symbol"] == f"{pair[0]}{pair[1]}":
                expiry_timestamp = 0
            else:
                date_arr = data["symbol"].split("_")
                if len(date_arr) > 1:
                    date_part = date_arr[1]
                    expiry_date = datetime.strptime(date_part, "%y%m%d")
                    expiry_date = expiry_date.replace(
                        hour=8, minute=0, second=0, tzinfo=timezone.utc
                    )
                    expiry_timestamp = int(expiry_date.timestamp())
                else:
                    expiry_timestamp = int(0)
            result_arr.append(
                FutureEntry(
                    pair_id=pair_id,
                    price=price_int,
                    volume=int(volume),
                    timestamp=int(timestamp / 1000),
                    source=self.SOURCE,
                    publisher=self.publisher,
                    expiry_timestamp=expiry_timestamp * 1000,
                    autoscale_volume=True,
                )
            )
        return result_arr
