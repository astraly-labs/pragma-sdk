import logging

from typing import Optional, Tuple, cast

from starknet_py.net.full_node_client import FullNodeClient
from pragma_sdk.common.types.types import Address
from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.abis.abi import ABIS, get_erc20_abi

logger = logging.getLogger(__name__)

Reserves = Tuple[int, int]


class LpContract:
    contract: Contract
    _token_0: Optional[Contract] = None
    _token_1: Optional[Contract] = None
    _decimals: Optional[int] = None

    def __init__(self, client: FullNodeClient, lp_address: Address):
        self.contract = Contract(
            address=lp_address,
            abi=ABIS["pragma_Pool"],
            provider=client,
            cairo_version=1,
        )

    async def get_reserves(self) -> Reserves:
        """Fetches reserves from the pool."""
        response = await self.contract.functions["get_reserves"].call(
            block_hash="pending"
        )
        return cast(Reserves, response[0])

    async def get_total_supply(self) -> int:
        """Fetches the total supply from the pool."""
        response = await self.contract.functions["total_supply"].call(
            block_hash="pending"
        )
        return int(response[0])

    async def get_decimals(self) -> int:
        """Returns the decimals of the pool."""
        if self._decimals is None:
            response = await self.contract.functions["decimals"].call(
                block_hash="pending"
            )
            self._decimals = int(response[0])
        return self._decimals

    async def get_token_0(self) -> Contract:
        """Returns the token 0 address from the pool."""
        if self._token_0 is None:
            token_0_address = await self.contract.functions["token_0"].call(
                block_hash="pending"
            )
            self._token_0 = Contract(
                address=token_0_address[0],
                abi=get_erc20_abi(),
                provider=self.contract.client,
                cairo_version=0,
            )
        return self._token_0

    async def get_token_1(self) -> Contract:
        """Returns the token 1 address from the pool."""
        if self._token_1 is None:
            token_1_address = await self.contract.functions["token_1"].call(
                block_hash="pending"
            )
            self._token_1 = Contract(
                address=token_1_address[0],
                abi=get_erc20_abi(),
                provider=self.contract.client,
                cairo_version=0,
            )
        return self._token_1
