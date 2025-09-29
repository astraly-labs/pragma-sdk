from typing import List
from abc import ABC, abstractmethod

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.utils import add_sync_methods

from pragma_sdk.onchain.types import PublishEntriesOnChainResult


@add_sync_methods
class PragmaClient(ABC):
    @abstractmethod
    async def publish_entries(
        self, entries: List[Entry]
    ) -> PublishEntriesOnChainResult:
        """
        Publish entries to some destination.

        :param entries: List of Entry objects
        :return: List of transaction invocation results
        """
