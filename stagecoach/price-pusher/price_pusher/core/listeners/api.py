from typing import Optional

from pragma.core.entry import Entry

from price_pusher.core.listeners.listener import PriceListener


class APIPriceListener(PriceListener):
    async def run_forever(self) -> None:
        raise NotImplementedError("TODO")

    async def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        raise NotImplementedError("TODO")

    async def fetch_latest_oracle_prices(self) -> None:
        raise NotImplementedError("TODO")
    
    