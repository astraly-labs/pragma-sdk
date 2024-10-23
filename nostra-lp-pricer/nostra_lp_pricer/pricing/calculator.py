
from nostra_lp_pricer.pool.contract import PoolContract
from nostra_lp_pricer.oracle.oracle import Oracle
from typing import Tuple
from nostra_lp_pricer.client import get_contract
from pragma_sdk.onchain.abis.abi import ABIS, get_erc20_abi
from nostra_lp_pricer.types import Reserves, TARGET_DECIMALS

class PoolPriceCalculator:
    def __init__(self, pool: PoolContract, oracle: Oracle):
        self.pool = pool
        self.oracle = oracle

    async def compute_lp_price(self, tokens: Tuple[int, int], reserves: Reserves, total_supply: int) -> int:
        """Computes the LP price based on reserves and total supply."""

        token_0_contract = get_contract(self.pool.network, tokens[0], get_erc20_abi(), cairo_version=0)
        token_1_contract = get_contract(self.pool.network, tokens[1], get_erc20_abi(), cairo_version=0)
        (token_0_price, token_0_decimals) = await self.oracle.get_token_price_and_decimals(token_0_contract)
        (token_1_price, token_1_decimals) = await self.oracle.get_token_price_and_decimals(token_1_contract)
        # Adjust token 0 price to 18 decimals
        if token_0_decimals < TARGET_DECIMALS:
            token_0_price = token_0_price * 10 ** (TARGET_DECIMALS - token_0_decimals)
        elif token_0_decimals > TARGET_DECIMALS:
            token_0_price = token_0_price // 10 ** (token_0_decimals - TARGET_DECIMALS)
        
        # Adjust token 1 price to 18 decimals
        if token_1_decimals < TARGET_DECIMALS:
            token_1_price = token_1_price * 10 ** (TARGET_DECIMALS - token_1_decimals)
        elif token_1_decimals > TARGET_DECIMALS:
            token_1_price = token_1_price // 10 ** (token_1_decimals - TARGET_DECIMALS)
        
        # Calculate LP price with normalized values
        lp_price = (reserves[0] * token_0_price + reserves[1] * token_1_price) // total_supply
        return lp_price
