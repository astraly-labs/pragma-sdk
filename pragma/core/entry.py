from __future__ import annotations

import abc
from typing import Dict, List, Optional, Tuple, Union

from pragma.core.assets import get_asset_spec_for_pair_id_by_type
from pragma.core.utils import felt_to_str, str_to_felt


class Entry(abc.ABC):
    @abc.abstractmethod
    def to_tuple(self) -> Tuple: ...

    @abc.abstractmethod
    def serialize(self) -> Dict[str, str]: ...

    @abc.abstractmethod
    def offchain_serialize(self) -> Dict[str, str]: ...

    @staticmethod
    def serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        # TODO (#000): log errors
        serialized_entries = [
            # TODO (#000): This needs to be much more resilient to publish errors
            entry.serialize()
            for entry in entries
            if isinstance(entry, Entry)
        ]
        return list(filter(lambda item: item is not None, serialized_entries))

    @staticmethod
    def offchain_serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        # TODO (#000): log errors
        serialized_entries = [
            # TODO (#000): This needs to be much more resilient to publish errors
            entry.offchain_serialize()
            for entry in entries
            if isinstance(entry, Entry)
        ]
        return list(filter(lambda item: item is not None, serialized_entries))

    @staticmethod
    def flatten_entries(entries: List[Entry]) -> List[int]:
        """This flattens entriees to tuples.  Useful when you need the raw felt array"""
        expanded = [entry.to_tuple() for entry in entries]
        flattened = [x for entry in expanded for x in entry]
        return [len(entries)] + flattened


class BaseEntry:
    timestamp: int
    source: int
    publisher: int

    def __init__(
        self, timestamp: int, source: Union[str, int], publisher: Union[str, int]
    ):
        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.timestamp = timestamp
        self.source = source
        self.publisher = publisher


class SpotEntry(Entry):
    """
    Represents a Spot Entry.

    ⚠️ By default, the constructor will autoscale the provided volume to be quoted in the base asset.
    This behavior can be overwritten witht the `autoscale_volume` parameter.
    """

    base: BaseEntry
    pair_id: int
    price: int
    volume: int

    def __init__(
        self,
        pair_id: Union[str, int],
        price: int,
        timestamp: int,
        source: Union[str, int],
        publisher: Union[str, int],
        volume: Optional[float] = 0,
        autoscale_volume: bool = True,
    ) -> None:
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)

        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.base = BaseEntry(timestamp, source, publisher)
        self.pair_id = pair_id
        self.price = price

        if volume > 0 and autoscale_volume:
            asset = get_asset_spec_for_pair_id_by_type(felt_to_str(pair_id), "SPOT")
            decimals = asset["decimals"] or 0
            volume = volume or 0

            self.volume = int(volume * price * 10**decimals)
        else:
            self.volume = volume

    def __eq__(self, other):
        if isinstance(other, SpotEntry):
            return (
                self.pair_id == other.pair_id
                and self.price == other.price
                and self.base.timestamp == other.base.timestamp
                and self.base.source == other.base.source
                and self.base.publisher == other.base.publisher
                and self.volume == other.volume
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, Tuple) and len(other) == 4:
            return (
                self.pair_id == other.pair_id
                and self.price == other.price
                and self.base.timestamp == other.base.timestamp
                and self.base.source == other.base.source
                and self.base.publisher == other.base.publisher
                and self.volume == other.volume
            )
        return False

    def to_tuple(self):
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.volume,
        )

    def serialize(self) -> Dict[str, str]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": self.base.source,
                "publisher": self.base.publisher,
            },
            "pair_id": self.pair_id,
            "price": self.price,
            "volume": self.volume,
        }

    def offchain_serialize(self) -> Dict[str, str]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": felt_to_str(self.base.source),
                "publisher": felt_to_str(self.base.publisher),
            },
            "pair_id": felt_to_str(self.pair_id),
            "price": self.price,
            "volume": self.volume,
        }

    def set_publisher(self, publisher):
        self.base.publisher = publisher
        return self

    @staticmethod
    def from_dict(entry_dict: Dict[str, str]) -> "SpotEntry":
        base = dict(entry_dict["base"])
        return SpotEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            volume=entry_dict["volume"],
            autoscale_volume=False,
        )

    def __repr__(self):
        return (
            f'SpotEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}, volume={self.volume})")'
        )


class FutureEntry(Entry):
    """
    Represents a Future Entry.

    Also used to represent a Perp Entry - the only difference is that a perpetual future has no
    expiry timestamp.

    ⚠️ By default, the constructor will autoscale the provided volume to be quoted in the base asset.
    This behavior can be overwritten witht the `autoscale_volume` parameter.
    """

    base: BaseEntry
    pair_id: int
    price: int
    expiry_timestamp: int
    volume: int

    def __init__(
        self,
        pair_id: Union[str, int],
        price: int,
        timestamp: int,
        source: Union[str, int],
        publisher: Union[str, int],
        expiry_timestamp: Optional[int] = 0,
        volume: Optional[float] = 0,
        autoscale_volume: Optional[bool] = True,
    ):
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)

        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.base = BaseEntry(timestamp, source, publisher)
        self.pair_id = pair_id
        self.price = price
        self.expiry_timestamp = expiry_timestamp

        if autoscale_volume:
            asset = get_asset_spec_for_pair_id_by_type(felt_to_str(pair_id), "FUTURE")
            decimals = asset["decimals"] or 0
            volume = volume or 0

            self.volume = int(volume * price * 10**decimals)
        else:
            self.volume = volume

    def __eq__(self, other):
        if isinstance(other, FutureEntry):
            return (
                self.pair_id == other.pair_id
                and self.price == other.price
                and self.base.timestamp == other.base.timestamp
                and self.base.source == other.base.source
                and self.base.publisher == other.base.publisher
                and self.expiry_timestamp == other.expiry_timestamp
                and self.volume == other.volume
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, Tuple) and len(other) == 4:
            return (
                self.pair_id == other.pair_id
                and self.price == other.price
                and self.base.timestamp == other.base.timestamp
                and self.base.source == other.base.source
                and self.base.publisher == other.base.publisher
                and self.expiry_timestamp == other.expiry_timestamp
                and self.volume == other.volume
            )
        return False

    def to_tuple(self) -> Tuple:
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.expiry_timestamp,
            self.volume,
        )

    def serialize(self) -> Dict[str, str]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": self.base.source,
                "publisher": self.base.publisher,
            },
            "pair_id": self.pair_id,
            "price": self.price,
            "expiration_timestamp": self.expiry_timestamp,
            "volume": self.volume,
        }

    def offchain_serialize(self) -> Dict[str, str]:
        serialized = {
            "base": {
                "timestamp": self.base.timestamp,
                "source": felt_to_str(self.base.source),
                "publisher": felt_to_str(self.base.publisher),
            },
            "pair_id": felt_to_str(self.pair_id),
            "price": self.price,
            "volume": self.volume,
            "expiration_timestamp": self.expiry_timestamp,
        }
        return serialized

    def __repr__(self):
        return (
            f'FutureEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, "
            f"timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}, '
            f"volume={self.volume}, "
            f'expiry_timestamp={self.expiry_timestamp})")'
        )

    @staticmethod
    def from_dict(entry_dict: Dict[str, str]) -> "FutureEntry":
        base = dict(entry_dict["base"])
        return FutureEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            entry_dict["expiration_timestamp"],
            volume=entry_dict["volume"],
            autoscale_volume=False,
        )
