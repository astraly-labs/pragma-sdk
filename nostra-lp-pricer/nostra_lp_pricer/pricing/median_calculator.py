
from nostra_lp_pricer.pool.data_store import PoolDataStore
from nostra_lp_pricer.pool.contract import PoolContract
from typing import Tuple
from nostra_lp_pricer.pricing.calculator import PoolPriceCalculator 
from nostra_lp_pricer.oracle.oracle import Oracle
from nostra_lp_pricer.pool.data_fetcher import PricePusher
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class MedianCalculator:
    def __init__(self, pool_store: PoolDataStore, pool_contract: PoolContract, oracle: Oracle, price_pusher: PricePusher, push_interval: int):
        self.pool_store = pool_store
        self.pool_contract = pool_contract
        self.oracle = oracle
        self.price_pusher = price_pusher
        self.push_interval = push_interval

    async def calculate_and_push_median(self, tokens: Tuple[int, int]):
        """Periodically calculates and pushes the lp price to the on-chain contract."""
        while True:
            try:
                median_supply = self.pool_store.calculate_median_supply()
                median_reserves = self.pool_store.calculate_median_reserves()

                logger.info(f"Calculated median - Supply: {median_supply}, Reserves: {median_reserves}")

                # Compute LP price and push data (currently placeholder)
                lp_price = await PoolPriceCalculator(self.pool_contract, self.oracle).compute_lp_price(
                    tokens, median_reserves, median_supply
                )

                invocation = await self.price_pusher.push_price(int(self.pool_contract.address,16), lp_price)
                await invocation.wait_for_acceptance()
                logger.info(f"Pushed median data to on-chain contract at {time.time()} with LP price {lp_price}")

                # TODO: add the deployed contract and push the price there
            except Exception as e:
                logger.error(f"Error pushing data to contract: {e}")
            await asyncio.sleep(self.push_interval)

