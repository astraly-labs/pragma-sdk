import logging

from typing import Optional
from abc import ABC, abstractmethod

from pragma.common.types.entry import Entry
from pragma.common.assets import PragmaAsset
from pragma.publisher.client import PragmaClient

logger = logging.getLogger(__name__)


class IRequestHandler(ABC):
    """
    Responsible of querying new prices from our oracles and returning entries.
    """

    client: PragmaClient

    @abstractmethod
    async def fetch_latest_entry(self, asset: PragmaAsset) -> Optional[Entry]: ...
