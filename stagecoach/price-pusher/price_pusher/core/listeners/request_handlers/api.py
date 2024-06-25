from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry
from pragma.publisher.client import PragmaAPIClient

from price_pusher.core.listeners.listener import IRequestHandler


class APIRequestHandler(IRequestHandler):
    client: PragmaAPIClient

    def __init__(self, client: PragmaAPIClient) -> None:
        self.client = client

    async def fetch_latest_asset_price(self, asset: PragmaAsset) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by request handler childrens.")
