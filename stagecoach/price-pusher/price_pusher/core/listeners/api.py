from typing import Optional

from price_pusher.core.listeners.listener import PriceListener

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry


class APIPriceListener(PriceListener):
    async def _fetch_latest_oracle_pair_price(
        self, asset: PragmaAsset
    ) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by children listener.")
