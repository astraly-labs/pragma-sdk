import asyncio
import logging
import os
import time
from typing import List

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, SpotEntry, FutureEntry
from pragma_sdk.onchain.client import PragmaOnChainClient


logger = logging.getLogger(__name__)


# You can fetch your data using any strategy or libraries you want
def fetch_entries(pairs: List[Pair], *args, **kwargs) -> List[Entry]:
    entries: List[Entry] = []

    for pair in pairs:
        entries.append(
            SpotEntry(
                timestamp=int(time.time()),
                source="MY_SOURCE",
                publisher="MY_PUBLISHER",
                pair_id=pair.id,
                price=10 * 10 ** pair.decimals(),  # shifted 10 ** decimals
                volume=0,
            )
        )
        entries.append(
            FutureEntry(
                timestamp=int(time.time()),
                source="MY_SOURCE",
                publisher="MY_PUBLISHER",
                pair_id=pair.id,
                price=10 * 10 ** pair.decimals(),  # shifted 10 ** decimals
                expiry_timestamp=1693275381,  # Set to 0 for perpetual contracts
                volume=0,
            )
        )

    return entries


async def publish_all(pairs: List[Pair]):
    # We get the keystore password and address of the account deployed in step 1.
    keystore_password = int(os.environ.get("PUBLISHER_KEYSTORE_PAD"), 0)
    publisher_address = int(os.environ.get("PUBLISHER_ADDRESS"), 0)

    publisher_client = PragmaOnChainClient(
        account_private_key=("/path/to/keystore", keystore_password),
        account_contract_address=publisher_address,
        network=os.environ["NETWORK"],  # ENV var set to `sepolia | mainnet`
    )

    # Use your own custom logic
    _entries = fetch_entries(pairs)
    await publisher_client.publish_many(_entries)

    logger.info("Publishing the following entries:")
    for entry in _entries:
        logger.info(entry, logger=logger)


PAIRS_TO_PUBLISH = [
    Pair.from_tickers("ETH", "USD"),
    Pair.from_tickers("BTC", "USD"),
    Pair.from_tickers("WBTC", "USD"),
]

if __name__ == "__main__":
    asyncio.run(publish_all(PAIRS_TO_PUBLISH))
