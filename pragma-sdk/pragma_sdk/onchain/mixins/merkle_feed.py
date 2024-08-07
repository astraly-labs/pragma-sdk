from typing import Optional
from starknet_py.contract import InvokeResult
from starknet_py.net.client import Client
from starknet_py.net.account.account import Account
from starknet_py.cairo.felt import encode_shortstring

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import OptionData

from pragma_sdk.common.utils import felt_to_str
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.types import Contract, MerkleProof, BlockId


class MerkleFeedMixin:
    """
    Class used to retrieve values from the Deribit options Merkle Feed.
    The Merkle Feed is in fact a merkle root stored in a GenericEntry.
    """

    client: Client
    account: Account
    summary_stats: Contract
    execution_config: ExecutionConfig

    async def get_options_data(
        self,
        instrument_name: int | str,
        block_id: Optional[BlockId] = "latest",
    ) -> OptionData:
        """
        Returns the latest OptionData for the given instrument name.
        """
        if isinstance(instrument_name, str):
            instrument_name = encode_shortstring(instrument_name.upper())

        (response,) = await self.summary_stats.functions["get_options_data"].call(
            instrument_name, block_number=block_id
        )
        response = dict(response)

        return OptionData(
            instrument_name=felt_to_str(response["instrument_name"]),
            base_currency=felt_to_str(response["base_currency_id"]),
            current_timestamp=response["current_timestamp"],
            mark_price=response["mark_price"],
        )

    async def update_options_data(
        self,
        merkle_proof: MerkleProof,
        update_data: OptionData,
    ) -> InvokeResult:
        """
        Update the Option data upon merkle proof verification.
        """
        invocation = await self.summary_stats.functions["update_options_data"].invoke(
            merkle_proof,
            update_data.serialize(),
            execution_config=self.execution_config,
        )
        return invocation
