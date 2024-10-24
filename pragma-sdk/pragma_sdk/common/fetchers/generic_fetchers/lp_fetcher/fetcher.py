import time
import asyncio

from statistics import median
from typing import Optional, List, Dict, Tuple
from aiohttp import ClientSession

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.types.entry import Entry, GenericEntry
from pragma_sdk.common.types.types import Address
from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.lp_contract import (
    LpContract,
    Reserves,
)
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.redis_manager import (
    LpRedisManager,
)
from pragma_sdk.onchain.types import Contract

from pragma_sdk.onchain.types import Network

TARGET_DECIMALS = 18

# We are storing into Redis the history of Reserves & Supply every 3 minutes.
# So we know that 10 data points means that we published for at least 30 minutes.
# This is the minimum number of points decided so that the computations make sense.
MINIMUM_DATA_POINTS = 10

logger = get_pragma_sdk_logger()


class LPFetcher(FetcherInterfaceT):
    """
    This Fetcher needs a Redis Database.
    """

    network: Network
    publisher: str
    pairs: List[Address]  # type: ignore[assignment]
    lp_contracts: Dict[Address, LpContract]
    redis_manager: LpRedisManager

    SOURCE: str = "PRAGMA"

    def __init__(
        self,
        pairs: List[Address],
        publisher: str,
        redis_manager: LpRedisManager,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        super().__init__(pairs, publisher, api_key, network)  # type: ignore[arg-type]
        self.network = network
        self.redis_manager = redis_manager
        self.lp_contracts: Dict[Address, LpContract] = dict()
        for address in pairs:
            self.lp_contracts[address] = LpContract(
                client=self.client.full_node_client,
                lp_address=address,
            )

    async def fetch(  # type: ignore[assignment]
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Construct a list of GenericEntry containing the pricing of
        the each LP Contract (contained in `self.pairs`) in parallel.
        They are all returned as `GenericEntry`.
        """
        tasks = [
            self.fetch_pair(lp_contract_address, session)
            for lp_contract_address in self.pairs
        ]
        entries = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(entries)
        return entries  # type: ignore[override]

    async def fetch_pair(
        self,
        pair: Address,  # type: ignore[override]
        session: ClientSession,
    ) -> Entry | PublisherFetchError:
        """
        Fetches the data for a specific pool address from the fetcher and returns a Generic object.
        """
        lp_contract = self.lp_contracts[pair]
        token_0 = await lp_contract.get_token_0()
        token_1 = await lp_contract.get_token_1()

        if not await self.store_latest_values(lp_contract=lp_contract):
            raise ValueError("Could not store latest values into Redis!")
        logger.info("👷 Stored the latest Pool values into Redis.")

        reserves = await self.get_median_reserves(lp_contract=lp_contract)
        if isinstance(reserves, PublisherFetchError):
            return reserves

        total_supply = await self.get_median_total_supply(lp_contract=lp_contract)
        if isinstance(total_supply, PublisherFetchError):
            return total_supply

        lp_price = await self.compute_lp_price(
            token_0=token_0,
            token_1=token_1,
            reserves=reserves,
            total_supply=total_supply,
        )

        return GenericEntry(
            key=pair,
            value=int(lp_price),
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )

    async def store_latest_values(self, lp_contract: LpContract) -> bool:
        latest_reserves = await lp_contract.get_reserves()
        latest_total_supply = await lp_contract.get_total_supply()
        return self.redis_manager.store_pool_data(
            network=self.network,
            pool_address=lp_contract.contract.address,
            reserves=latest_reserves,
            total_supply=latest_total_supply,
        )

    async def get_median_reserves(
        self, lp_contract: LpContract
    ) -> Reserves | PublisherFetchError:
        """
        Stores the latest reserves in Redis & computes the median reserves.
        Works only if we have at least 10 data points of history stored in Redis.
        """
        history_reserves = self.redis_manager.get_latest_n_reserves(
            network=self.network,
            pool_address=lp_contract.contract.address,
            n=MINIMUM_DATA_POINTS,
        )
        if len(history_reserves) < MINIMUM_DATA_POINTS:
            return PublisherFetchError(
                "Can't compute Lp Price - not enough history for the Pool reserves."
            )

        token_0_reserves = [x[0] for x in history_reserves]
        token_1_reserves = [x[1] for x in history_reserves]
        return (int(median(token_0_reserves)), int(median(token_1_reserves)))

    async def get_median_total_supply(
        self, lp_contract: LpContract
    ) -> int | PublisherFetchError:
        """
        Stores the latest total supply and computes the median of the total supply.
        Works only if we have at least 10 data points of history stored in Redis.
        """
        history_total_supply = self.redis_manager.get_latest_n_total_supply(
            network=self.network,
            pool_address=lp_contract.contract.address,
            n=MINIMUM_DATA_POINTS,
        )

        if len(history_total_supply) < MINIMUM_DATA_POINTS:
            return PublisherFetchError(
                "Can't compute Lp Price - not enough history for the Pool total supply."
            )

        total_supply = int(median(history_total_supply))
        return total_supply

    async def compute_lp_price(
        self,
        token_0: Contract,
        token_1: Contract,
        reserves: Reserves,
        total_supply: int,
    ) -> int:
        """
        Computes the LP price based on reserves and total supply.
        Takes into consideration the decimals of the fetched prices.
        """

        (token_0_price, token_0_decimals) = await self.get_token_price_and_decimals(
            token_0
        )
        (token_1_price, token_1_decimals) = await self.get_token_price_and_decimals(
            token_1
        )

        # Adjust token 0 price to TARGET_DECIMALS (18)
        if token_0_decimals < TARGET_DECIMALS:
            token_0_price = token_0_price * 10 ** (TARGET_DECIMALS - token_0_decimals)
        elif token_0_decimals > TARGET_DECIMALS:
            token_0_price = token_0_price // 10 ** (token_0_decimals - TARGET_DECIMALS)

        # Adjust token 1 price to TARGET_DECIMALS (18)
        if token_1_decimals < TARGET_DECIMALS:
            token_1_price = token_1_price * 10 ** (TARGET_DECIMALS - token_1_decimals)
        elif token_1_decimals > TARGET_DECIMALS:
            token_1_price = token_1_price // 10 ** (token_1_decimals - TARGET_DECIMALS)

        # Calculate LP price with normalized values
        lp_price = (
            (reserves[0] * token_0_price) + (reserves[1] * token_1_price)
        ) // total_supply
        return lp_price

    async def get_token_price_and_decimals(self, token: Contract) -> Tuple[int, int]:
        """Fetches the token price from the oracle."""
        token_pair = await self.get_token_pair(token)
        oracle_response = await self.client.get_spot(
            pair_id=str_to_felt(token_pair),
            block_id="pending",
        )
        return (oracle_response.price, oracle_response.decimals)

    async def get_token_pair(self, token: Contract) -> str:
        """Gets the token/USD pair symbol."""
        token_symbol = await token.functions["symbol"].call()
        return felt_to_str(token_symbol[0]) + "/USD"

    def format_url(self, pair: Pair) -> str:
        """Formats the URL for the fetcher, used in `fetch_pair` to get the data."""
        raise NotImplementedError("Not needed for LPFetcher.")
