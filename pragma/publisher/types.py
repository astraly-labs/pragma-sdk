import abc
from enum import Enum, unique
from typing import Any, List

import aiohttp
from aiohttp import ClientSession

from pragma.core.client import PragmaClient
from pragma.core.utils import add_sync_methods, str_to_felt


# Abstract base class for all publishers
@add_sync_methods
class PublisherInterfaceT(abc.ABC):
    client: PragmaClient

    @abc.abstractmethod
    async def fetch(self, session: ClientSession) -> List[Any]: ...

    @abc.abstractmethod
    def format_url(self, quote_asset, base_asset) -> str: ...

    async def _fetch(self):
        async with aiohttp.ClientSession() as session:
            data = await self.fetch(session)
            return data

    async def get_stable_price(self, stable_asset):
        usdt_str = str_to_felt(stable_asset + "/USD")
        usdt_entry = await self.client.get_spot(usdt_str)
        return int(usdt_entry.price) / (10 ** int(usdt_entry.decimals))


class PublisherFetchError(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __eq__(self, other):
        return self.message == other.message

    def __repr__(self):
        return self.message

    def serialize(self):
        return self.message


@unique
class Interval(Enum):
    ONE_MINUTE = "1min"
    FIFTEEN_MINUTES = "15min"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"

    def serialize(self):
        return {self.value: None}
