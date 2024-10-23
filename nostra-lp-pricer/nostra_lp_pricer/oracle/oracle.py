from pragma_sdk.common.utils import felt_to_str, str_to_felt
from nostra_lp_pricer.client import get_contract
from starknet_py.contract import Contract
from nostra_lp_pricer.types import Network, ORACLE_ADDRESSES
from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.common.types.asset import Asset
from pragma_sdk.common.types.types import DataTypes
from typing import Tuple

class Oracle:
    """
    Oracle class, used to fetch the token prices, decimals and build an asset pair out of a given currency
    """
    def __init__(self, network: Network):
        self.network = network
       
        self.oracle_address = int(ORACLE_ADDRESSES["sepolia"], 16) if network == "sepolia" else int(ORACLE_ADDRESSES["mainnet"], 16)
        self.contract = get_contract(network, self.oracle_address, ABIS["pragma_Oracle"])

    async def get_token_price_and_decimals(self, token: Contract) -> Tuple[int, int]:
        """Fetches the token price from the oracle."""
        token_pair = await self.get_token_pair(token)
        asset = await self.contract.functions["get_data_median"].call(
            Asset(DataTypes.SPOT, str_to_felt(token_pair), None).serialize(),
        )
        return (asset[0]["price"], asset[0]["decimals"])

    async def get_token_pair(self, token: Contract) -> str:
        """Gets the token/USD pair symbol."""
        token_symbol = await token.functions["symbol"].call()
        return felt_to_str(token_symbol[0]) + '/USD'
