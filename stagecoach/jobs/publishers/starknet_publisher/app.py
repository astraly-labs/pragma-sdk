import asyncio
import json
import os

import boto3

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
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
    PropellerFetcher,
    StarknetAMMFetcher,
)
from pragma.publisher.future_fetchers import (
    BinanceFutureFetcher,
    ByBitFutureFetcher,
    OkxFutureFetcher,
)

logger = get_stream_logger()

NETWORK = os.environ["NETWORK"]
SECRET_NAME = os.environ["SECRET_NAME"]
SPOT_ASSETS = os.environ["SPOT_ASSETS"]
FUTURE_ASSETS = os.environ["FUTURE_ASSETS"]
PUBLISHER = os.environ.get("PUBLISHER")
PUBLISHER_ADDRESS = int(os.environ.get("PUBLISHER_ADDRESS"), 16)
PROPELLER_API_KEY = os.environ.get("PROPELLER_API_KEY")
PAGINATION = os.environ.get("PAGINATION")
RPC_URL = os.environ.get("RPC_URL")
MAX_FEE = int(os.getenv("MAX_FEE", int(1e17)))

DEVIATION_THRESHOLD = float(os.getenv("DEVIATION_THRESHOLD", 0.01))
FREQUENCY_SECONDS = int(os.getenv("FREQUENCY_SECONDS", 60))

if PAGINATION is not None:
    PAGINATION = int(PAGINATION)


def handler(event, context):
    spot_assets = [
        get_spot_asset_spec_for_pair_id(asset) for asset in SPOT_ASSETS.split(",")
    ]
    future_assets = [
        get_future_asset_spec_for_pair_id(asset) for asset in FUTURE_ASSETS.split(",")
    ]
    spot_assets.extend(future_assets)
    entries_ = asyncio.run(_handler(spot_assets))
    return {
        "success": len(entries_),
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


async def _handler(assets):
    publisher_private_key = _get_pvt_key()
    # publisher_private_key = int(os.environ.get("PUBLISHER_PRIVATE_KEY"), 16)

    rpc_url = os.getenv("RPC_URL")

    if not rpc_url:
        publisher_client = PragmaPublisherClient(
            network=NETWORK,
            account_private_key=publisher_private_key,
            account_contract_address=PUBLISHER_ADDRESS,
        )
    else:
        publisher_client = PragmaPublisherClient(
            network=rpc_url + "/rpc",
            account_private_key=publisher_private_key,
            account_contract_address=PUBLISHER_ADDRESS,
            chain_name=os.getenv("NETWORK"),
        )

    last_publish = await publisher_client.get_time_since_last_published(
        "ETH/USD", PUBLISHER
    )
    deviation = await publisher_client.get_current_price_deviation("ETH/USD")
    print(f"Last publish was {last_publish} seconds ago and deviation is {deviation}")
    if last_publish < FREQUENCY_SECONDS and deviation < DEVIATION_THRESHOLD:
        print(
            f"Last publish was {last_publish} seconds ago and deviation is {deviation}, skipping publish"
        )
        return []

    publisher_client.add_fetchers(
        [
            fetcher(assets, PUBLISHER)
            for fetcher in (
                BitstampFetcher,
                DefillamaFetcher,
                OkxFetcher,
                GeckoTerminalFetcher,
                StarknetAMMFetcher,
                HuobiFetcher,
                KucoinFetcher,
                BybitFetcher,
                BinanceFetcher,
                BinanceFutureFetcher,
                OkxFutureFetcher,
                ByBitFutureFetcher,
            )
        ]
    )

    publisher_client.add_fetcher(PropellerFetcher(assets, PUBLISHER, PROPELLER_API_KEY))

    _entries = await publisher_client.fetch()
    print(_entries)
    response = await publisher_client.publish_many(
        _entries,
        pagination=PAGINATION,
        max_fee=MAX_FEE,
    )

    print(
        f"Published data with tx hashes: {', '.join([hex(res.hash) for res in response])}"
    )

    return _entries


if __name__ == "__main__":
    handler(None, None)
