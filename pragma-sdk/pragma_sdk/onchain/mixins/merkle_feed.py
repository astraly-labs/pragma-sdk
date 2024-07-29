from typing import Sequence
from starknet_py.net.client import Client
from starknet_py.net.account.account import Account


from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import OptionData
from pragma_sdk.onchain.types import Contract


class MerkleFeedMixin:
    """
    Class used to retrieve values from the Deribit options Merkle Feed.
    The Merkle Feed is in fact a merkle root stored in a GenericEntry.
    """

    client: Client
    account: Account
    summary_stats: Contract

    async def get_options_data() -> OptionData:
        raise NotImplementedError("🙅‍♀ get_options_data not implemented yet!")

    async def update_options_data(
        self, merkle_proof: Sequence[int], update_data: OptionData
    ) -> None:
        raise NotImplementedError("🙅‍♀ update_options_data not implemented yet!")
