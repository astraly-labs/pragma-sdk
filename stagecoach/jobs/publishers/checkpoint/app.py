import asyncio
import json
import os

import boto3

from pragma_sdk.common.assets import get_asset_spec_for_pair_id_by_type
from pragma_sdk.common.logger import get_stream_logger
from pragma_sdk.common.utils import currency_pair_to_pair_id
from pragma_sdk.publisher.client import PragmaOnChainClient

logger = get_stream_logger()

SECRET_NAME = os.environ["SECRET_NAME"]
NETWORK = os.environ["NETWORK"]
ASSETS = os.environ["ASSETS"]
ASSET_TYPE = os.environ.get("ASSET_TYPE", "SPOT")
ACCOUNT_ADDRESS = int(os.environ.get("ACCOUNT_ADDRESS"), 16)
MAX_FEE = int(os.environ.get("MAX_FEE", int(1e17)))


def handler(event, context):
    assets = [
        get_asset_spec_for_pair_id_by_type(asset.upper(), ASSET_TYPE)
        for asset in ASSETS.split(",")
    ]
    invocation = asyncio.run(_handler(assets))
    return {
        "result": invocation.hash,
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
    private_key = _get_pvt_key()

    publisher_client = PragmaOnChainClient(
        account_private_key=private_key,
        account_contract_address=ACCOUNT_ADDRESS,
        network=NETWORK,
    )

    pairs = [
        currency_pair_to_pair_id(*p["pair"]) for p in assets if p["type"] == ASSET_TYPE
    ]

    if ASSET_TYPE == "SPOT":
        invocation = await publisher_client.set_checkpoints(
            pairs, max_fee=MAX_FEE, pagination=40
        )
    else:
        invocation = await publisher_client.set_future_checkpoints(
            pairs, max_fee=MAX_FEE, pagination=40
        )

    print(f"Set checkpoints for pairs {pairs} at tx hash : {hex(invocation.hash)}")

    return invocation


if __name__ == "__main__":
    handler(None, None)
