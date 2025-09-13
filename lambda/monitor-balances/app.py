import asyncio
import json
import os

import boto3
import requests
import telegram
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.utils import felt_to_str

logger = get_pragma_sdk_logger()

# Inputs
# [Optional]: Publisher names; if empty, query for all
# [Optional]: Balance threshold; if empty, defaults to 100 * 10**18 Fri

# Behavior: Ping betteruptime iff all is good

SECRET_NAME = os.environ.get("SECRET_NAME")


def handler(event, context):
    asyncio.run(_handler())
    return {"success": True}


def _get_telegram_bot_oauth_token_from_aws():
    region_name = "eu-west-3"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(get_secret_value_response["SecretString"])[
        "TELEGRAM_BOT_USER_OAUTH_TOKEN"
    ]


async def _handler():
    chat_id = os.environ.get("CHAT_ID")
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_USER_OAUTH_TOKEN")
    if telegram_bot_token is None:
        telegram_bot_token = _get_telegram_bot_oauth_token_from_aws()
    network = os.environ.get("NETWORK")
    ignore_publishers_str = os.environ.get("IGNORE_PUBLISHERS", "")
    ignore_publishers = [
        int(p.strip()) for p in ignore_publishers_str.split(",") if p.strip()
    ]
    threshold_wei = int(os.environ.get("THRESHOLD_WEI", 100 * 10**18))
    bot = telegram.Bot(token=telegram_bot_token)
    client = PragmaOnChainClient(network)

    publishers = [
        publisher
        for publisher in await client.get_all_publishers()
        if publisher not in ignore_publishers
    ]

    all_above_threshold = True

    for publisher in publishers:
        address = await client.get_publisher_address(publisher)

        # STRK token address for gas fees
        token_address = (
            0x04718F5A0FC34CC1AF16A1CDEE98FFB20C31F5CD61D6AB07201858F4287C938D
        )
        balance = await client.get_balance(address, token_address)

        if balance < threshold_wei:
            error_message = f"Balance below threshold for publisher: {felt_to_str(publisher)}, address: {hex(address)}, balance in STRK: {balance/(10**18)}"
            logger.warning(error_message)
            all_above_threshold = False
            await bot.send_message(chat_id, text=error_message)

        else:
            logger.info(
                f"Balance above threshold for publisher: {felt_to_str(publisher)}, address: {hex(address)}, balance in STRK: {balance/(10**18)}"
            )

    if all_above_threshold:
        betteruptime_id = os.environ.get("BETTERUPTIME_ID")
        requests.get(f"https://betteruptime.com/api/v1/heartbeat/{betteruptime_id}")


if __name__ == "__main__":
    handler(None, None)
