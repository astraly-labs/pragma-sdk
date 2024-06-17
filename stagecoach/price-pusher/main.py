import asyncio
import json
import time
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
SPOT_ASSETS = os.environ.get("SPOT_ASSETS", "BTC/USD")
FUTURE_ASSETS = os.environ.get("FUTURE_ASSETS", "BTC/USDT")
PUBLISHER = os.environ["PUBLISHER"]
PUBLISHER_ADDRESS = int(os.environ.get("PUBLISHER_ADDRESS"), 16)
PROPELLER_API_KEY = os.environ.get("PROPELLER_API_KEY")
API_KEY = os.environ.get("API_KEY")
PAGINATION = os.environ.get("PAGINATION")
API_URL = os.environ.get("API_URL", "https://api.dev.pragma.build/node")
if PAGINATION is not None:
    PAGINATION = int(PAGINATION)


async def fetch_and_publish():
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
        logger.error(
            "No assets to publish. Check SPOT_ASSETS and FUTURE_ASSETS env variables."
        )
        return

    # publisher_private_key = _get_pvt_key()
    publisher_private_key = int(os.environ["PUBLISHER_PRIVATE_KEY"], 16)

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
    logger.info(f"Got {entries} entries")
    # response = await publisher_client.create_entries(entries)
    # logger.info(f"Successfully published data with response {response}")


# def _get_pvt_key():
#     region_name = "eu-west-3"

#     # Create a Secrets Manager client
#     session = boto3.session.Session()
#     client = session.client(service_name="secretsmanager", region_name=region_name)
#     get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
#     return int(
#         json.loads(get_secret_value_response["SecretString"])["PUBLISHER_PRIVATE_KEY"],
#         16,
#     )


async def main():
    while True:
        start_time = time.time()  # Record the start time
        try:
            await fetch_and_publish()
        except Exception as e:
            logger.error(f"Error occurred: {e}")
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        logger.info(f"fetch_and_publish took {duration:.2f} seconds")
        # await asyncio.sleep(10)  # Run every 10 seconds


if __name__ == "__main__":
    asyncio.run(main())
