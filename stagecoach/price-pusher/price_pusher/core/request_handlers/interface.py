import logging

from typing import Optional
from abc import ABC, abstractmethod

from pragma.core.entry import Entry
from pragma.core.assets import PragmaAsset
from pragma.publisher.client import PragmaPublisherClientT

logger = logging.getLogger(__name__)


class IRequestHandler(ABC):
    """
    Responsible of querying new prices from our oracles and returning entries.
    """

    client: PragmaPublisherClientT

    @abstractmethod
    async def fetch_latest_asset_price(self, asset: PragmaAsset) -> Optional[Entry]: ...
