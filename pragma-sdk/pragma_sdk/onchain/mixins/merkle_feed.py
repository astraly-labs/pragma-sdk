from starknet_py.net.client import Client
from starknet_py.net.account.account import Account

from pragma_sdk.onchain.types import Contract


class MerkleFeedMixin:
    """
    Class used to retrieve values from the Deribit options Merkle Feed.
    The Merkle Feed is in fact a merkle root stored in a GenericEntry.
    """

    client: Client
    account: Account
    summary_stats: Contract

    async def i_do_not_know_yet(self) -> None:
        raise NotImplementedError("🙅‍♀ i_do_not_know_yet not implemented yet!")
