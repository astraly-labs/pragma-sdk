import asyncio
import logging
import math
import time
from typing import List, Union

from aiohttp import ClientSession
from dotenv import load_dotenv
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import Call

from pragma.core.assets import PRAGMA_ALL_ASSETS, PragmaAsset

# from starknet_py.net.full_node_client import FullNodeClient
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.types import PoolKey
from pragma.core.utils import currency_pair_to_pair_id, str_to_felt
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

load_dotenv()

logging.basicConfig()
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


class StarknetAMMFetcher(PublisherInterfaceT):
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

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="mainnet")

    def prepare_call(self) -> Call:
        token_0, token_1 = (
            min(self.ETH_ADDRESS, self.STRK_ADDRESS),
            max(self.ETH_ADDRESS, self.STRK_ADDRESS),
        )
        fee = math.floor(self.POOL_FEE * 2**128)
        # An TICK_SPACING increaese of a price means the new price is price*(1+TICK_SPACING)
        # We want to know the number of tick for a price increase of TICK_SPACING
        # Since the tick spacing is represented as an exponent of TICK_BASE, we can use
        # the logarithm to find the number of tick
        tick = round(math.log(1 + self.TICK_SPACING) / math.log(self.TICK_BASE))
        pool_key = PoolKey(
            int(token_0, 16),
            int(token_1, 16),
            int(fee),
            int(tick),
            int(self.POOL_EXTENSION),
        )
        call = Call(
            to_addr=self.EKUBO_MAINNET_CORE_CONTRACT,
            selector=get_selector_from_name("get_pool_price"),
            calldata=pool_key.serialize(),
        )
        return call

    async def off_fetch_ekubo_price(
        self, asset, session: ClientSession, timestamp=None
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(asset["pair"][0], asset["pair"][1], timestamp)
        pair = asset["pair"]
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Starknet"
                )
            if resp.status == 200:
                result_json = await resp.json()
                return self._construct(asset, float(result_json["price"]))
            return await self.operate_eth_hop(asset, session)

    async def on_fetch_ekubo_price(self) -> float:
        call = self.prepare_call()
        pool_info = await self.client.full_node_client.call_contract(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (sqrt_ratio / 2**128) ** 2 * 10 ** (18)

    def format_url(self, base_asset, quote_asset, timestamp=None):
        # TODO: remove that
        if quote_asset == "USD":
            quote_asset = "USDC"
        if timestamp:
            return f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?atTime={timestamp}&period=3600"
        return f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?period=3600"

    async def operate_eth_hop(self, asset, session: ClientSession) -> SpotEntry:
        pair_1_str = str_to_felt("ETH/" + asset["pair"][1])
        pair_1_entry = await self.client.get_spot(pair_1_str)
        hop_asset = next(
            (
                cur_asset
                for cur_asset in PRAGMA_ALL_ASSETS
                if cur_asset["pair"] == ("ETH", asset["pair"][0])
            ),
            None,
        )
        if hop_asset["pair"] not in SUPPORTED_ASSETS:
            return PublisherFetchError("StarknetAMM: Hop asset not supported")
        pair2_entry = await self.off_fetch_ekubo_price(hop_asset, session)
        pair1_price = int(pair_1_entry.price) / (10 ** int(pair_1_entry.decimals))
        price = pair1_price / (pair2_entry.price / (10 ** int(hop_asset["decimals"])))
        return self._construct(asset, price)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT" and asset["pair"] in SUPPORTED_ASSETS:
                entries.append(
                    asyncio.ensure_future(self.off_fetch_ekubo_price(asset, session))
                )
            else:
                logger.debug(
                    "Skipping StarknetAMM for non ETH or non STRK pair: %s", asset
                )

        return await asyncio.gather(*entries, return_exceptions=True)

    def _construct(self, asset, result) -> SpotEntry:
        price_int = int(result * (10 ** asset["decimals"]))
        return SpotEntry(
            pair_id=currency_pair_to_pair_id(*asset["pair"]),
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=0,
        )
