import asyncio
import logging
import os
import time
from typing import List

from pragma_sdk.common.assets import PRAGMA_ALL_ASSETS, PragmaAsset
from pragma_sdk.common.types.entry import FutureEntry, SpotEntry
from pragma_sdk.common.utils import currency_pair_to_pair_id
from pragma_sdk.publisher.client import PragmaOnChainClient

logger = logging.getLogger(__name__)


def fetch_entries(assets: List[PragmaAsset], *args, **kwargs) -> List[SpotEntry]:
    entries = []

    for asset in assets:
        if asset["type"] == "ONCHAIN":
            continue

        if asset["type"] == "SPOT":
            entries.append(
                SpotEntry(
                    timestamp=int(time.time()),
                    source="MY_SOURCE",
                    publisher="MY_PUBLISHER",
                    pair_id=currency_pair_to_pair_id(*asset["pair"]),
                    price=10 * 10 ** asset["decimals"],  # shifted 10 ** decimals
                    volume=0,
                )
            )
        if asset["type"] == "FUTURE":
            entries.append(
                FutureEntry(
                    timestamp=int(time.time()),
                    source="MY_SOURCE",
                    publisher="MY_PUBLISHER",
                    pair_id=currency_pair_to_pair_id(*asset["pair"]),
                    price=10 * 10 ** asset["decimals"],  # shifted 10 ** decimals
                    expiry_timestamp=1693275381,  # Set to 0 for perpetual contracts
                    volume=0,
                )
            )

    return entries


async def publish_all(assets):
    max_fee = int(os.getenv("MAX_FEE", int(1e18)))
    # We get the private key and address of the account deployed in step 1.
    publisher_private_key = int(os.environ.get("PUBLISHER_PRIVATE_KEY"), 0)
    publisher_address = int(os.environ.get("PUBLISHER_ADDRESS"), 0)

    publisher_client = PragmaOnChainClient(
        account_private_key=publisher_private_key,
        account_contract_address=publisher_address,
        network=os.environ["NETWORK"],  # ENV var set to `testnet | mainnet`
    )

    # Use your own custom logic
    _entries = fetch_entries(assets)
    await publisher_client.publish_many(
        _entries, max_fee=int(max_fee), auto_estimate=True
    )

    logger.info("Publishing the following entries:")
    for entry in _entries:
        logger.info("Entry: %s", entry.serialize())


if __name__ == "__main__":
    asyncio.run(publish_all(PRAGMA_ALL_ASSETS))
