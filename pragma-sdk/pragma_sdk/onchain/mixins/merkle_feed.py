from typing import Any

from starknet_py.net.client import Client
from starknet_py.net.account.account import Account

from pragma_sdk.onchain.types import Contract


class MerkleFeedMixin:
    client: Client
    account: Account
    summary_stats: Contract

    async def publish_merkle_feed(self) -> None:
        raise NotImplementedError("🙅‍♀ publish_merkle_feed not implemented yet!")

    async def get_merkle_feed(self) -> Any:
        raise NotImplementedError("🙅‍♀ get_merkle_feed not implemented yet!")
