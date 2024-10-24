import logging
from typing import Union, Dict, Optional, Tuple

from starknet_py.net.account.account import Account

from pragma_sdk.common.types.types import Address

from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.abis.abi import ABIS, get_erc20_abi

logger = logging.getLogger(__name__)


Reserves = Tuple[int, int]

class LpContract:
    contract: Contract
    _token_0: Optional[Contract]
    _token_1: Optional[Contract]

    def __init__(self, account: Account, lp_address: Address):
        self.contract = Contract(
            address=self.contract_addresses_config.summary_stats_address,
            abi=ABIS["pragma_Pool"],
            provider=account,
            cairo_version=1,
        )
    
    async def init_tokens(self):
        self.token_0 = await self.get_token_0()
        self.token_1 = await self.get_token_1()

    async def get_reserves(self) -> Union[Reserves, Dict[str, str]]:
        """Fetches reserves from the pool."""
        return await self.contract.functions['get_reserves'].call()

    async def get_total_supply(self) -> int:
        """Fetches the total supply from the pool."""
        return await self.contract.functions['total_supply'].call()

    async def get_token_0(self) -> Contract:
        """Fetches the token 0 address from the pool."""
        if self._token_0 is None:
            token_0_address = await self.contract.functions['token_0'].call()
            self._token_0 = Contract(address=token_0_address, abis=get_erc20_abi(), cairo_version=0)
        return self._token_0
    
    async def get_token_1(self) -> Contract: 
        """Fetches the token 1 address from the pool."""
        if self._token_1 is None:
            token_1_address = await self.contract.functions['token_1'].call()
            self._token_1 = Contract(address=token_1_address, abis=get_erc20_abi(), cairo_version=0)
        return self._token_1
