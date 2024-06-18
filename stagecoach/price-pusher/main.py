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


def load_env_variables():
    return {
        "SECRET_NAME": os.environ.get("SECRET_NAME", None),
        "SPOT_ASSETS": os.environ.get("SPOT_ASSETS", "BTC/USD"),
        "FUTURE_ASSETS": os.environ.get("FUTURE_ASSETS", "BTC/USDT"),
        "PUBLISHER": os.environ.get("PUBLISHER", "PRAGMA"),
        "PUBLISHER_ADDRESS": int(os.environ.get("PUBLISHER_ADDRESS"), 16),
        "PROPELLER_API_KEY": os.environ.get("PROPELLER_API_KEY"),
        "API_KEY": os.environ.get("API_KEY"),
        "PAGINATION": (
            int(os.environ.get("PAGINATION", 0))
            if os.environ.get("PAGINATION")
            else None
        ),
        "API_URL": os.environ.get("API_URL", "https://api.dev.pragma.build/node"),
    }


def get_asset_specs(assets_str, get_asset_spec_func):
    return [
        get_asset_spec_func(asset) for asset in assets_str.split(",") if len(asset) > 0
    ]


async def fetch_and_publish(env_vars):
    spot_assets = get_asset_specs(
        env_vars["SPOT_ASSETS"], get_spot_asset_spec_for_pair_id
    )
    future_assets = get_asset_specs(
        env_vars["FUTURE_ASSETS"], get_future_asset_spec_for_pair_id
    )

    if not spot_assets and not future_assets:
        logger.error(
            "No assets to publish. Check SPOT_ASSETS and FUTURE_ASSETS env variables."
        )
        return

    # publisher_private_key = int(os.environ["PUBLISHER_PRIVATE_KEY"], 16)
    publisher_private_key = _get_pvt_key(env_vars["SECRET_NAME"])

    publisher_client = PragmaAPIClient(
        account_private_key=publisher_private_key,
        account_contract_address=env_vars["PUBLISHER_ADDRESS"],
        api_base_url=env_vars["API_URL"],
        api_key=env_vars["API_KEY"],
    )

    fetcher_client = PragmaPublisherClient()
    add_fetchers(fetcher_client, spot_assets, env_vars["PUBLISHER"])

    entries = await fetcher_client.fetch()
    logger.info(f"Got {entries} entries")
    # response = await publisher_client.create_entries(entries)
    # logger.info(f"Successfully published data with response {response}")


def _get_pvt_key(secret_name):
    region_name = "eu-west-3"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    return int(
        json.loads(get_secret_value_response["SecretString"])["PUBLISHER_PRIVATE_KEY"],
        16,
    )


def add_fetchers(fetcher_client, spot_assets, publisher):
    fetchers = [
        DefillamaFetcher,
        # BitstampFetcher,
        # CexFetcher,
        # OkxFetcher,
        # GeckoTerminalFetcher,
        # HuobiFetcher,
        # KucoinFetcher,
        # BybitFetcher,
        # BinanceFetcher,
    ]
    fetcher_client.add_fetchers(
        [fetcher(spot_assets, publisher) for fetcher in fetchers]
    )

    # Uncomment to add PropellerFetcher
    # fetcher_client.add_fetcher(PropellerFetcher(spot_assets, publisher, PROPELLER_API_KEY))

    # Uncomment to add future fetchers
    # future_fetchers = [
    #     BinanceFutureFetcher,
    #     ByBitFutureFetcher,
    # ]
    # fetcher_client.add_fetchers([fetcher(future_assets, publisher) for fetcher in future_fetchers])


async def main():
    env_vars = load_env_variables()
    while True:
        start_time = time.time()
        try:
            await fetch_and_publish(env_vars)
        except Exception as e:
            logger.error(f"Error occurred: {e}")
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"fetch_and_publish took {duration:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
