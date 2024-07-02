import asyncio
import logging
import time
from typing import Any, List, Union

from aiohttp import ClientSession

from pragma.common.types.entry import SpotEntry
from pragma.common.types.pair import Pair
from pragma.offchain.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_ASSETS = [
    ("ETH", "STRK"),
    ("STRK", "USD"),
    ("STRK", "USDT"),
    ("LORDS", "USD"),
    ("ETH", "LORDS"),
    ("ZEND", "USD"),
    ("ZEND", "USDC"),
    ("ZEND", "USDT"),
    ("ETH", "ZEND"),
    ("NSTR", "USD"),
    ("NSTR", "USDC"),
    ("NSTR", "USDT"),
    ("ETH", "NSTR"),
]


class StarknetAMMFetcher(FetcherInterfaceT):
    EKUBO_PUBLIC_API: str = "https://mainnet-api.ekubo.org"
    EKUBO_MAINNET_CORE_CONTRACT: str = (
        "0x00000005dd3d2f4429af886cd1a3b08289dbcea99a294197e9eb43b0e0325b4b"
    )
    PRAGMA_ORACLE_CONTRACT: str = (
        "0x2a85bd616f912537c50a49a4076db02c00b29b2cdc8a197ce92ed1837fa875b"
    )
    # Parameters for the pool

    # These are the parameters of the most used pool in Ekubo for the testing pair ETH/USDC
    POOL_FEE = 0.0005  # 0.05%
    TICK_SPACING = 0.001  # 0.1%
    TICK_BASE = 1.000001
    POOL_EXTENSION = 0

    STRK_ADDRESS: str = (
        "0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d"
    )
    ETH_ADDRESS: str = (
        "0x049D36570D4e46f48e99674bd3fcc84644DdD6b96F7C741B1562B82f9e004dC7"
    )
    ETH_DECIMALS: int = 8
    STRK_DECIMALS: int = 8

    SOURCE = "STARKNET"

    async def off_fetch_ekubo_price(
        self, pair: Pair, session: ClientSession, timestamp=None
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair, timestamp)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Starknet"
                )
            if resp.status == 200:
                result_json = await resp.json()
                return self._construct(pair, float(result_json["price"]))
            return await self.operate_eth_hop(pair, session)

    def format_url(self, pair: Pair, timestamp=None):
        # TODO: remove that
        quote_pair = pair.quote_currency.id
        if quote_pair == "USD":
            quote_pair = "USDC"
        if timestamp:
            return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{quote_pair}?atTime={timestamp}&period=3600"
        return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{quote_pair}?period=3600"

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for pair in self.pairs:
            if pair.to_tuple() in SUPPORTED_ASSETS:
                entries.append(
                    asyncio.ensure_future(self.off_fetch_ekubo_price(pair, session))
                )
            else:
                logger.debug(
                    "Skipping StarknetAMM for non ETH or non STRK pair: %s", pair
                )

        return await asyncio.gather(*entries, return_exceptions=True)

    def _construct(self, pair: Pair, result: Any) -> SpotEntry:
        price_int = int(result * (10 ** pair.decimals()))
        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=0,
        )
