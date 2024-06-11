import asyncio
import json
import os

from pragma.core.assets import (
    get_future_asset_spec_for_pair_id,
    get_spot_asset_spec_for_pair_id,
)
from pragma.core.logger import get_stream_logger
from pragma.publisher.client import PragmaPublisherClient
from pragma.publisher.fetchers import (
    BinanceFetcher,
    BitstampFetcher,
    BybitFetcher,
    CexFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
)
from pragma.publisher.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher
from pragma.publisher.perp_fetchers import BinancePerpFetcher

logger = get_stream_logger()

SPOT_ASSETS = os.environ["SPOT_ASSETS"]
FUTURE_ASSETS = os.environ["FUTURE_ASSETS"]
PUBLISHER = os.environ["PUBLISHER"]
PUBLISHER_ADDRESS = int(os.environ.get("PUBLISHER_ADDRESS"), 16)
API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL", "https://api.dev.pragma.build/node")


def handler(event, context):
    assets = [
        get_future_asset_spec_for_pair_id(asset) for asset in FUTURE_ASSETS.split(",")
    ]
    response = asyncio.run(_handler(assets))
    return {
        "success": response,
    }


async def _handler(assets):
    # publisher_private_key = _get_pvt_key()
    publisher_private_key = int(os.environ["PUBLISHER_PRIVATE_KEY"], 16)

    publisher_client = PragmaPublisherClient(
        account_private_key=publisher_private_key,
        account_contract_address=PUBLISHER_ADDRESS,
        api_url=API_URL,
        api_key=API_KEY,
    )

    publisher_client.add_fetchers(
        [fetcher(assets, PUBLISHER) for fetcher in [ByBitFutureFetcher]]
    )

    entries = await publisher_client.fetch()
    response = await publisher_client.publish_data(entries)

    return response


if __name__ == "__main__":
    handler(None, None)
