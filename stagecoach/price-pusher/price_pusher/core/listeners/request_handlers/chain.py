from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry
from pragma.publisher.client import PragmaOnChainClient

from price_pusher.core.listeners.listener import IRequestHandler


class ChainRequestHandler(IRequestHandler):
    client: PragmaOnChainClient

    def __init__(self, client: PragmaOnChainClient) -> None:
        self.client = client

    async def fetch_latest_asset_price(self, asset: PragmaAsset) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by request handler childrens.")
