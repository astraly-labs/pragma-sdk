import asyncio
import json
import logging
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class KaikoFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://us.market-api.kaiko.io/v2/data/trades.v1/spot_direct_exchange_rate"
    )
    SOURCE: str = "KAIKO"
    payload = {
        "interval": "1d",
        "page_size": "1",
        "extrapolate_missing_values": "true",
    }

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, api_key: str = ""):
        self.assets = assets
        self.publisher = publisher
        self.headers = {"X-Api-Key": api_key}

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}/{pair[0].lower()}/{pair[1].lower()}"

        async with session.get(url, headers=self.headers, params=self.payload) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kaiko"
                )

            if resp.status == 403:
                return PublisherFetchError(
                    "Unauthorized: Please provide an API Key to use KaikoFetcher"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"KAIKO: Unexpected content type: {content_type}")

            if "error" in result and result["error"] == "Invalid Symbols Pair":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kaiko"
                )

            return self._construct(asset, result)

    def _fetch_pair_sync(
        self, asset: PragmaSpotAsset
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}/{pair[0].lower()}/{pair[1].lower()}"

        resp = requests.get(url, headers=self.headers, params=self.payload)

        if resp.status_code == 404:
            return PublisherFetchError(f"No data found for {'/'.join(pair)} from Kaiko")

        if resp.status_code == 403:
            return PublisherFetchError(
                "Unauthorized: Please provide an API Key to use KaikoFetcher"
            )

        text = resp.text
        result = json.loads(text)

        if "error" in result and result["error"] == "Invalid Symbols Pair":
            return PublisherFetchError(f"No data found for {'/'.join(pair)} from Kaiko")

        return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Kaiko for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Kaiko for non-spot asset %s", asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        url = (
            f"{self.BASE_URL}/{quote_asset.lower()}/{base_asset.lower()}"
            + "?extrapolate_missing_values=true&interval=1d&page_size=1"
        )
        return url

    def _construct(self, asset, result) -> SpotEntry:
        data = result["data"][0]
        pair = asset["pair"]

        timestamp = int(result["timestamp"])
        price = float(data["price"])
        price_int = int(price * (10 ** asset["decimals"]))
        volume = float(data["volume"])
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from Kaiko", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            volume=volume,
            publisher=self.publisher,
        )
