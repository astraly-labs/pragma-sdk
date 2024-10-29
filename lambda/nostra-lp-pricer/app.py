import asyncio
import os
import time

import requests
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.onchain.client import PragmaOnChainClient

logger = get_pragma_sdk_logger()

# Behavior: Ping betteruptime if all is good

MAX_TIME_DIFFERENCE = 600 # 10 minutes

def handler(event, context):
    asyncio.run(_handler())
    return {"success": True}


async def _handler():
    network = os.environ.get("NETWORK", "mainnet")
    betteruptime_id = os.environ.get("BETTERUPTIME_ID")

    # Get generic entry for one pool (ETH/USDC)
    client = PragmaOnChainClient(network)
    entry = await client.get_generic(
        int("0x05e03162008d76cf645fe53c6c13a7a5fce745e8991c6ffe94400d60e44c210a", 16)
    )

    now = time.time()
    all_good = now - entry.base.timestamp < MAX_TIME_DIFFERENCE

    if all_good:
        logger.info("All good, pinging BetterUptime")
        requests.get(f"https://betteruptime.com/api/v1/heartbeat/{betteruptime_id}")


if __name__ == "__main__":
    handler(None, None)
