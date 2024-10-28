from typing import Optional, Tuple, cast, List

from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.hash.selector import get_selector_from_name

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.types import Address
from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.abis.abi import ABIS, get_erc20_abi

logger = get_pragma_sdk_logger()

Reserves = Tuple[int, int]

REQUIRED_POOL_FUNCTIONS: List[int] = [
    get_selector_from_name("get_reserves"),
    get_selector_from_name("total_supply"),
    get_selector_from_name("decimals"),
    get_selector_from_name("token_0"),
    get_selector_from_name("token_1"),
]

# The address is the same for mainnet/sepolia
MULTICALL_CONTRACT_ADDRESS = int(
    "0x05754af3760f3356da99aea5c3ec39ccac7783d925a19666ebbeca58ff0087f4", 16
)


class LpContract:
    contract: Contract
    _token_0: Optional[Contract] = None
    _token_1: Optional[Contract] = None
    _decimals: Optional[int] = None

    def __init__(
        self, client: FullNodeClient, lp_address: Address, block_hash="pending"
    ):
        self.contract = Contract(
            address=lp_address,
            abi=ABIS["pragma_Pool"],
            provider=client,
            cairo_version=1,
        )
        self.block_hash = block_hash

    async def is_valid(self) -> bool:
        """
        Validate that the current contract is valid and usable.
        We query every functions to make sure that it exists on-chain.
        """
        try:
            multicaller = await Contract.from_address(
                provider=self.contract.client,
                address=MULTICALL_CONTRACT_ADDRESS,
            )
            calls = [
                {
                    "to": self.contract.address,
                    "selector": selector,
                    "data_offset": 0,
                    "data_len": 0,
                }
                for selector in REQUIRED_POOL_FUNCTIONS
            ]
            _ = await multicaller.functions["aggregate"].call(calls, [])
        except Exception as _:
            logger.error(
                f"⛔ The contract {hex(self.contract.address)} is not a valid pool. "
                "Ignoring - it won't be priced."
            )
            return False

        return True

    async def get_reserves(self) -> Reserves:
        """Fetches reserves from the pool."""
        response = await self.contract.functions["get_reserves"].call(
            block_hash=self.block_hash
        )
        return cast(Reserves, response[0])

    async def get_total_supply(self) -> int:
        """Fetches the total supply from the pool."""
        response = await self.contract.functions["total_supply"].call(
            block_hash=self.block_hash
        )
        return int(response[0])

    async def get_decimals(self) -> int:
        """Returns the decimals of the pool."""
        if self._decimals is None:
            response = await self.contract.functions["decimals"].call(
                block_hash=self.block_hash
            )
            self._decimals = int(response[0])
        return self._decimals

    async def get_token_0(self) -> Contract:
        """Returns the token 0 address from the pool."""
        if self._token_0 is None:
            token_0_address = await self.contract.functions["token_0"].call(
                block_hash=self.block_hash
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
                block_hash=self.block_hash
            )
            self._token_1 = Contract(
                address=token_1_address[0],
                abi=get_erc20_abi(),
                provider=self.contract.client,
                cairo_version=0,
            )
        return self._token_1
