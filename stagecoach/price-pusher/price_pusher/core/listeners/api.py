from typing import Optional

from pragma.core.entry import Entry

from price_pusher.core.listeners.listener import PriceListener


class APIPriceListener(PriceListener):
    async def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        raise NotImplementedError("TODO")

    async def _fetch_latest_oracle_pair_price(self) -> None:
        raise NotImplementedError("TODO")
