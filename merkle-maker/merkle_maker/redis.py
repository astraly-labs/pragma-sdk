import json

from typing import Any
from json import JSONEncoder

from redis import Redis
from pragma_sdk.common.fetchers.generic_fetchers.deribit import CurrenciesOptions, OptionData


class OptionDataJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, OptionData):
            return {
                "instrument_name": obj.instrument_name,
                "base_currency": obj.base_currency,
                "current_timestamp": obj.current_timestamp,
                "mark_price": int(obj.mark_price),
            }
        return super().default(obj)


class RedisManager:
    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store(self, key: str, value: Any):
        self.client.set(key, value)

    def store_options(self, key: str, options: CurrenciesOptions):
        options = json.dumps(options, cls=OptionDataJSONEncoder)
        self.store(key, options)

    def get(self, key: str):
        return self.client.get(key)
