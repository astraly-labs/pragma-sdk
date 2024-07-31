import logging

from typing import List, Optional
from abc import ABC, abstractmethod

from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.client import PragmaClient

logger = logging.getLogger(__name__)


class IRequestHandler(ABC):
    """
    Responsible of querying new prices from our oracles and returning entries.
    """

    client: PragmaClient

    @abstractmethod
    async def fetch_latest_entries(
        self,
        pair: Pair,
        data_type: DataTypes,
        sources: Optional[List[str]] = None,
    ) -> List[Entry]: ...
