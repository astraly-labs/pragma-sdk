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

    async def validate_pools(self) -> None:
        """
        Must be called after the Fetcher init.
        We check that all Lp Contracts are indeed supported by the Oracle.
        """
        lp_addresses = list(self.lp_contracts.keys())
        for lp_address in lp_addresses:
            await self._validate_pool(lp_address)

    async def _validate_pool(self, lp_address: Address) -> None:
        """
        Checks if a pool is valid and removes it from the list if it is not.
        """
        lp_contract = self.lp_contracts[lp_address]
        pool_is_valid = (await lp_contract.is_valid()) and (
            await self._are_currencies_registered(lp_contract)
        )
        if not pool_is_valid:
            del self.lp_contracts[lp_address]

    async def _are_currencies_registered(
        self,
        lp_contract: LpContract,
    ) -> bool:
        """
        Returns true if the underlying assets of a Pool are correctly registered on-chain on the Oracle.
        """
        token_0 = await lp_contract.get_token_0()
        token_0_symbol = await token_0.functions["symbol"].call()
        token_0_symbol = felt_to_str(token_0_symbol[0])
        token_1 = await lp_contract.get_token_1()
        token_1_symbol = await token_1.functions["symbol"].call()
        token_1_symbol = felt_to_str(token_1_symbol[0])

        are_supported = (await self.client.is_currency_registered(token_0_symbol)) and (
            await self.client.is_currency_registered(token_1_symbol)
        )

        if not are_supported:
            logger.error(
                f"⛔ The underlying assets of the pool {hex(lp_contract.contract.address)} are not"
                " supported by Pragma Oracle. The pool will not be priced."
            )
        return are_supported

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

        if not await self._store_latest_values(lp_contract=lp_contract):
            raise ValueError("Could not store latest values into Redis!")

        reserves = await self._get_median_reserves(lp_contract=lp_contract)
        if isinstance(reserves, PublisherFetchError):
            return reserves

        total_supply = await self._get_median_total_supply(lp_contract=lp_contract)
        if isinstance(total_supply, PublisherFetchError):
            return total_supply

        decimals = await lp_contract.get_decimals()

        lp_price = await self._compute_lp_price(
            token_0=token_0,
            token_1=token_1,
            reserves=reserves,
            total_supply=total_supply,
            decimals=decimals,
        )
        if isinstance(lp_price, PublisherFetchError):
            return lp_price

        return GenericEntry(
            key=pair,
            value=int(lp_price),
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )

    async def _store_latest_values(self, lp_contract: LpContract) -> bool:
        """
        Store the latest reserves and total supply into redis.
        """
        latest_reserves = await lp_contract.get_reserves()
        latest_total_supply = await lp_contract.get_total_supply()
        return self.redis_manager.store_pool_data(
            network=self.network,
            pool_address=lp_contract.contract.address,
            reserves=latest_reserves,
            total_supply=latest_total_supply,
        )

    async def _get_median_reserves(
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

    async def _get_median_total_supply(
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

    async def _compute_lp_price(
        self,
        token_0: Contract,
        token_1: Contract,
        reserves: Reserves,
        total_supply: int,
        decimals: int,
    ) -> float | PublisherFetchError:
        """
        Computes the LP price based on reserves and total supply.
        Takes into consideration the decimals of the fetched prices.
        """
        response = await self._get_token_price_and_decimals(token_0)
        if isinstance(response, PublisherFetchError):
            return response
        (token_0_price, token_0_decimals, token_0_price_decimals) = response

        response = await self._get_token_price_and_decimals(token_1)
        if isinstance(response, PublisherFetchError):
            return response
        (token_1_price, token_1_decimals, token_1_price_decimals) = response

        # Scale the token prices & reserves to the pool decimals
        (scaled_token_0_price, reserve_0) = self._adjust_decimals(
            token_0_price,
            reserves[0],
            token_0_decimals,
            token_0_price_decimals,
            decimals,
        )
        (scaled_token_1_price, reserve_1) = self._adjust_decimals(
            token_1_price,
            reserves[1],
            token_1_decimals,
            token_1_price_decimals,
            decimals,
        )

        # Compute the LP price
        lp_price = (
            (reserve_0 * scaled_token_0_price) + (reserve_1 * scaled_token_1_price)
        ) / total_supply
        return lp_price

    def _adjust_decimals(
        self,
        price: int,
        reserve: int,
        decimals: int,
        price_decimals: int,
        target_decimals: int,
    ) -> Tuple[float, float]:
        """
        Adjust the decimals of the prices and the reserves to the target decimals.
        """
        if price_decimals < target_decimals:
            price = price * 10 ** (target_decimals - price_decimals)
        elif price_decimals > target_decimals:
            price = price / 10 ** (price_decimals - target_decimals)

        if decimals < target_decimals:
            reserve = reserve * 10 ** (target_decimals - decimals)
        elif decimals > target_decimals:
            reserve = reserve / 10 ** (decimals - target_decimals)

        return (price, reserve)

    async def _get_token_price_and_decimals(
        self, token: Contract, block_id: str = "pending"
    ) -> Tuple[int, int, int] | PublisherFetchError:
        """
        For a given token contract, return:
            * the price in USD for the token,
            * the decimals of the token,
            * the decimals of the USD price.
        """
        token_pair = await self._get_pair_usd_quoted(token)
        oracle_response = await self.client.get_spot(
            pair_id=str_to_felt(token_pair),
            block_id=block_id,
        )
        if oracle_response.price == 0 and oracle_response.last_updated_timestamp == 0:
            return PublisherFetchError(
                f"No prices found for pair {token_pair}. " "Can't compute the LP price."
            )
        token_decimals = await token.functions["decimals"].call()
        return (oracle_response.price, token_decimals[0], oracle_response.decimals)

    async def _get_pair_usd_quoted(self, token: Contract) -> str:
        """
        For the given token contract, fetch the symbol and returns the token quoted
        to USD as a `Pair`.
        """
        token_symbol = await token.functions["symbol"].call()
        return felt_to_str(token_symbol[0]) + "/USD"

    def format_url(self, pair: Pair) -> str:
        """
        Not used in this fetcher! But needed to comply with the Fetcher interface.
        """
        raise NotImplementedError("Not needed for LPFetcher.")
