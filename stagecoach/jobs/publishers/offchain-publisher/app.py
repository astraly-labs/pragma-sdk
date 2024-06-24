import asyncio
import json
import os

import boto3

from pragma.core.assets import (
    get_future_asset_spec_for_pair_id,
    get_spot_asset_spec_for_pair_id,
)
from pragma.core.logger import get_stream_logger
from pragma.publisher.client import PragmaAPIClient, PragmaPublisherClient
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
    PropellerFetcher,
)
from pragma.publisher.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher

logger = get_stream_logger()

SECRET_NAME = os.environ.get("SECRET_NAME", None)
SPOT_ASSETS = os.environ.get("SPOT_ASSETS", "")
FUTURE_ASSETS = os.environ.get("FUTURE_ASSETS", "")
PUBLISHER = os.environ["PUBLISHER"]
PUBLISHER_ADDRESS = int(os.environ.get("PUBLISHER_ADDRESS"), 16)
PROPELLER_API_KEY = os.environ.get("PROPELLER_API_KEY")
API_KEY = os.environ.get("API_KEY")
PAGINATION = os.environ.get("PAGINATION")
API_URL = os.environ.get("API_URL", "https://api.dev.pragma.build")
if PAGINATION is not None:
    PAGINATION = int(PAGINATION)


def handler(event, context):
    spot_assets = [
        get_spot_asset_spec_for_pair_id(asset)
        for asset in SPOT_ASSETS.split(",")
        if len(asset) > 0
    ]
    future_assets = [
        get_future_asset_spec_for_pair_id(asset)
        for asset in FUTURE_ASSETS.split(",")
        if len(asset) > 0
    ]
    if len(spot_assets) == 0 and len(future_assets) == 0:
        return {
            "success": False,
            "message": "No assets to publish. Check SPOT_ASSETS and FUTURE_ASSETS env variables.",
        }
    response = asyncio.run(_handler(spot_assets, future_assets))
    return {
        "success": response,
    }


def _get_pvt_key():
    region_name = "eu-west-3"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
    return int(
        json.loads(get_secret_value_response["SecretString"])["PUBLISHER_PRIVATE_KEY"],
        16,
    )


async def _handler(spot_assets, future_assets):
    publisher_private_key = _get_pvt_key()
    # publisher_private_key = int(os.environ["PUBLISHER_PRIVATE_KEY"], 16)

    publisher_client = PragmaAPIClient(
        account_private_key=publisher_private_key,
        account_contract_address=PUBLISHER_ADDRESS,
        api_base_url=API_URL,
        api_key=API_KEY,
    )

    fetcher_client = PragmaPublisherClient()

    fetcher_client.add_fetchers(
        [
            fetcher(spot_assets, PUBLISHER)
            for fetcher in (
                BitstampFetcher,
                CexFetcher,
                DefillamaFetcher,
                OkxFetcher,
                GeckoTerminalFetcher,
                HuobiFetcher,
                KucoinFetcher,
                BybitFetcher,
                BinanceFetcher,
            )
        ]
    )
    fetcher_client.add_fetcher(
        PropellerFetcher(spot_assets, PUBLISHER, PROPELLER_API_KEY)
    )
    fetcher_client.add_fetchers(
        [
            fetcher(future_assets, PUBLISHER)
            for fetcher in (
                BinanceFutureFetcher,
                ByBitFutureFetcher,
            )
        ]
    )

    entries = await fetcher_client.fetch()
    print(f"Got {entries} entries")
    response = await publisher_client.create_entries(entries)
    print(f"Successfuly published data with response {response}")

    return response


if __name__ == "__main__":
    handler(None, None)
