from pragma.core.assets import PragmaSpotAsset, PragmaFutureAsset, get_asset_spec_for_pair_id_by_type, PragmaAsset
from pragma.core.entry import SpotEntry, FutureEntry, Entry
from typing import List, Optional, Dict
from typing_extensions import Annotated
from enum import Enum

from pydantic import BaseModel, field_validator, RootModel, Field, ConfigDict
from abc import ABC, abstractmethod
import asyncio

class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs_spot: Optional[List[PragmaSpotAsset]] = None
    pairs_future: Optional[List[PragmaFutureAsset]] = None
    time_difference: Annotated[int, Field(strict=True, gt=0)] 
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator('pairs_spot', mode="before")
    def validate_pairs_spot(cls, value):
        assets: List[PragmaSpotAsset] = []
        for pair in value:
            pair = pair.replace(' ', '').upper()
            splitted = pair.split('/')
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")
            
            asset = get_asset_spec_for_pair_id_by_type(pair, "SPOT")
            assets.append(asset)

        return assets
    
    @field_validator('pairs_future', mode="before")
    def validate_pairs_future(cls, value):
        assets: List[PragmaFutureAsset] = []
        for pair in value:
            pair = pair.replace(' ', '').upper()
            splitted = pair.split('/')
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")
            
            asset = get_asset_spec_for_pair_id_by_type(pair, "FUTURE")
            assets.append(asset)

        return assets


class PriceConfigFile(RootModel):
    root: List[PriceConfig]


class Envirronment(Enum):
    DEV = 1
    PROD = 2

class DataSource(Enum):
    ONCHAIN = 1
    OFFCHAIN = 2
    DEFILLAMA = 3

UnixTimestamp = int
DurationInSeconds = int

class IPriceListener(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        pass


class ChainPriceListener(IPriceListener, ABC):
    def __init__(self, polling_frequency: DurationInSeconds, price_items: List[PragmaAsset]) -> None:
        self.polling_frequency = polling_frequency
        self.price_items = price_items
        self.latest_price_info: Dict[str, Entry] = {}

    async def start(self) -> None:
        await self.poll_prices()
        while True:
            await asyncio.sleep(self.polling_frequency)
            await self.poll_prices()

    async def poll_prices(self) -> None:
        for item in self.price_items:
            current_price_info = await self.get_on_chain_price_info(item.id)
            if current_price_info:
                self.update_latest_price_info(item.id, current_price_info)

    def update_latest_price_info(self, pair_id: str, observed_price: Entry) -> None:
        cached_latest_price_info: Optional[Entry] = self.get_latest_price_info(pair_id)

        if cached_latest_price_info and cached_latest_price_info.get_timestamp() > observed_price.get_timestamp():
            return

        self.latest_price_info[pair_id] = observed_price

    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        return self.latest_price_info.get(pair_id)

    @abstractmethod
    async def get_on_chain_price_info(self, pair_id: str) -> Optional[Entry]:
        pass


class IPricePusher(ABC):
    @abstractmethod
    async def update_price_feed(self, pair_ids: List[str], pub_times_to_push: List[UnixTimestamp]) -> None:
        pass

