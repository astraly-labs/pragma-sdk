from typing import Optional
from starknet_py.net.client import Client
from starknet_py.net.account.account import Account


from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import OptionData
from pragma_sdk.onchain.types import Contract, MerkleProof, BlockId


class MerkleFeedMixin:
    """
    Class used to retrieve values from the Deribit options Merkle Feed.
    The Merkle Feed is in fact a merkle root stored in a GenericEntry.
    """

    client: Client
    account: Account
    summary_stats: Contract

    async def get_options_data(
        self,
        block_id: Optional[BlockId] = "latest",
    ) -> OptionData:
        """
        Returns the latest OptionData.
        """
        (response,) = await self.summary_stats.functions["get_options_data"].call(
            block_number=block_id
        )
        return OptionData(**dict(response))

    async def update_options_data(
        self,
        merkle_proof: MerkleProof,
        update_data: OptionData,
    ) -> None:
        """
        Update the Option data upon merkle proof verification.
        """
        print(self.summary_stats.functions)
        (response,) = await self.summary_stats.functions["update_options_data"].call(
            merkle_proof,
            update_data.serialize(),
        )
