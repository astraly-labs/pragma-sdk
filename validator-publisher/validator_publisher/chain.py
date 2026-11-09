"""
Reads and calls on the staking contract and the ValidatorRegistry, as raw
calls: the staking views are decoded against the layout deployed on mainnet
and sepolia (@staking/contracts-v1.0.1-dev.854).
"""

from dataclasses import dataclass
from typing import List, Optional

import aiohttp
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import Call
from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.common.utils import felt_to_str, str_to_felt

from validator_publisher.deployments import STAKING_CONTRACTS, STRK_TOKEN

OPTION_SOME = 0
SPOT_VARIANT = 0
# variant, base (timestamp, source, publisher), price, pair_id, volume
SPOT_ENTRY_FELTS = 7


@dataclass(frozen=True)
class OracleSpotEntry:
    timestamp: int
    source: int
    publisher: int
    price: int


def decode_spot_entries(result: List[int]) -> List[OracleSpotEntry]:
    """Decode `get_data_entries -> Span<PossibleEntries>` for a spot pair."""
    entries, idx = [], 1
    for _ in range(result[0]):
        if result[idx] != SPOT_VARIANT:
            raise ValueError(f"not a spot entry: variant {result[idx]}")
        timestamp, source, publisher, price = result[idx + 1 : idx + 5]
        entries.append(OracleSpotEntry(timestamp, source, publisher, price))
        idx += SPOT_ENTRY_FELTS
    return entries


@dataclass(frozen=True)
class StakerInfo:
    reward_address: int
    operational_address: int
    unstake_time: Optional[int]
    amount_own: int


def decode_staker_info(result: List[int]) -> Optional[StakerInfo]:
    """Decode `get_staker_info_v1 -> Option<StakerInfoV1>`."""
    if result[0] != OPTION_SOME:
        return None
    reward_address, operational_address = result[1], result[2]
    if result[3] == OPTION_SOME:
        unstake_time, idx = result[4], 5
    else:
        unstake_time, idx = None, 4
    return StakerInfo(reward_address, operational_address, unstake_time, result[idx])


def call(to: int, entrypoint: str, calldata: List[int]) -> Call:
    return Call(
        to_addr=to, selector=get_selector_from_name(entrypoint), calldata=calldata
    )


class PilotChain:
    def __init__(self, rpc_url: str, network: str, registry: int, oracle: int) -> None:
        self.rpc_url = rpc_url
        self.client = FullNodeClient(node_url=rpc_url)
        self.registry = registry
        self.oracle = oracle
        self.staking = STAKING_CONTRACTS[network]

    async def _read(self, to: int, entrypoint: str, calldata: List[int]) -> List[int]:
        return await self.client.call_contract(  # type: ignore[no-any-return]
            call(to, entrypoint, calldata), block_number="latest"
        )

    async def rpc(self, method: str) -> object:
        payload = {"jsonrpc": "2.0", "id": 0, "method": method, "params": []}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.rpc_url, json=payload) as response:
                body = await response.json()
        if "error" in body:
            raise RuntimeError(f"{method}: {body['error']}")
        return body["result"]

    async def staker_info(self, staker: int) -> Optional[StakerInfo]:
        return decode_staker_info(
            await self._read(self.staking, "get_staker_info_v1", [staker])
        )

    async def publisher_status(self, staker: int) -> str:
        (status,) = await self._read(self.registry, "get_publisher_status", [staker])
        return felt_to_str(status)

    async def oracle_signer(self, staker: int) -> int:
        (signer,) = await self._read(self.registry, "get_oracle_signer", [staker])
        return signer

    async def declared_staker(self, signer: int) -> int:
        (staker,) = await self._read(self.registry, "get_declared_staker", [signer])
        return staker

    async def allowed_sources(self) -> List[int]:
        result = await self._read(self.registry, "get_allowed_sources", [])
        return list(result[1 : 1 + result[0]])

    async def spot_entries(self, pair: str) -> List[OracleSpotEntry]:
        """Every publisher's entry per source, as the pilot Oracle aggregates them."""
        return decode_spot_entries(
            await self._read(
                self.oracle, "get_data_entries", [SPOT_VARIANT, str_to_felt(pair)]
            )
        )

    async def decimals(self, pair: str) -> int:
        (decimals,) = await self._read(
            self.oracle, "get_decimals", [SPOT_VARIANT, str_to_felt(pair)]
        )
        return decimals

    async def block_timestamp(self) -> int:
        block = await self.client.get_block(block_number="latest")
        return block.timestamp  # type: ignore[no-any-return]

    async def min_self_stake(self) -> int:
        (amount,) = await self._read(self.registry, "get_min_self_stake", [])
        return amount

    async def strk_balance(self, account: int) -> int:
        low, high = await self._read(STRK_TOKEN, "balance_of", [account])
        return low + (high << 128)

    async def is_deployed(self, address: int) -> bool:
        try:
            await self.client.get_class_hash_at(address, block_number="latest")
        except Exception:
            return False
        return True

    def declare_call(self, staker: int) -> Call:
        return call(self.registry, "declare_oracle_signer", [staker])

    def bind_call(self, signer: int) -> Call:
        return call(self.registry, "bind_oracle_signer", [signer])

    def revoke_call(self, staker: int) -> Call:
        return call(self.registry, "revoke_oracle_signer", [staker])
