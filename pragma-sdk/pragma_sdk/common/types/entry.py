from __future__ import annotations

import abc

from datetime import datetime
from pydantic.dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import StrEnum

from pragma_sdk.common.types.types import DataTypes, UnixTimestamp
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.onchain.types.types import OracleResponse
from pragma_sdk.schema import entries_pb2


FUTURE_ENTRY_EXPIRIES_FORMAT = "%Y-%m-%dT%H:%M:%S"


class Entry(abc.ABC):
    """
    Abstract class that represents an Entry.
    All entries must implement this class.
    """

    @abc.abstractmethod
    def to_tuple(self) -> Tuple[Any]: ...

    @abc.abstractmethod
    def serialize(self) -> Dict[str, object]: ...

    @abc.abstractmethod
    def offchain_serialize(self) -> Dict[str, object]: ...

    @abc.abstractmethod
    def get_timestamp(self) -> int: ...

    @abc.abstractmethod
    def get_expiry(self) -> Optional[str]: ...

    @abc.abstractmethod
    def get_pair_id(self) -> str: ...

    @abc.abstractmethod
    def get_source(self) -> str: ...

    @abc.abstractmethod
    def get_asset_type(self) -> DataTypes: ...

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> Optional["Entry"]: ...

    @staticmethod
    def serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        serialized_entries = [entry.serialize() for entry in entries]
        return list(filter(lambda item: item is not None, serialized_entries))  # type: ignore[arg-type]

    @staticmethod
    def offchain_serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        serialized_entries = [entry.offchain_serialize() for entry in entries]
        return list(filter(lambda item: item is not None, serialized_entries))  # type: ignore[arg-type]

    @staticmethod
    def flatten_entries(entries: List[Entry]) -> List[int]:
        """This flattens entriees to tuples. Useful when you need the raw felt array"""

        expanded = [entry.to_tuple() for entry in entries]
        flattened = [x for entry in expanded for x in entry]
        return [len(entries)] + flattened


@dataclass
class BaseEntry:
    """
    BaseEntry is a dataclass that represents the common fields between SpotEntry and FutureEntry.
    """

    timestamp: UnixTimestamp
    source: int
    publisher: int

    def __init__(
        self,
        timestamp: UnixTimestamp,
        source: str | int,
        publisher: str | int,
    ):
        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.timestamp = timestamp
        self.source = source
        self.publisher = publisher

    def __hash__(self) -> int:
        return hash((self.timestamp, self.source, self.publisher))


class SpotEntry(Entry):
    """
    Represents a Spot Entry.
    """

    base: BaseEntry
    pair_id: int
    price: int
    volume: int

    def __init__(
        self,
        pair_id: str | int,
        price: int,
        timestamp: UnixTimestamp,
        source: str | int,
        publisher: str | int,
        volume: Optional[int | float] = None,
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

        if volume is None:
            volume = 0
        if isinstance(volume, float):
            volume = int(volume)
        self.volume = volume

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SpotEntry):
            return all(
                [
                    self.pair_id == other.pair_id,
                    self.price == other.price,
                    self.base.timestamp == other.base.timestamp,
                    self.base.source == other.base.source,
                    self.base.publisher == other.base.publisher,
                    self.volume == other.volume,
                ]
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, tuple) and len(other) == 4:
            return all(
                [
                    self.pair_id == other[0],
                    self.price == other[1],
                    self.base == other[2],
                    self.volume == other[3],
                ]
            )
        return False

    def to_tuple(self) -> Tuple[int, int, int, int, int, int]:  # type: ignore[explicit-override, override]
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.volume,
        )

    def serialize(self) -> Dict[str, object]:
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

    def offchain_serialize(self) -> Dict[str, object]:
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

    def set_publisher(self, publisher: int) -> "SpotEntry":
        self.base.publisher = publisher
        return self

    def get_timestamp(self) -> int:
        return self.base.timestamp

    def get_expiry(self) -> Optional[str]:
        return None

    def get_pair_id(self) -> str:
        return felt_to_str(self.pair_id)

    def get_source(self) -> str:
        return felt_to_str(self.base.source)

    def get_asset_type(self) -> DataTypes:
        return DataTypes.SPOT

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> Optional["SpotEntry"]:
        """
        Builds a SpotEntry object from a Pair and an OracleResponse.
        Method primarly used by our price pusher package when we're retrieving
        lastest oracle prices for comparisons with the latest prices of
        various APIs (binance etc).
        """
        if oracle_response.last_updated_timestamp == 0:
            return None

        return SpotEntry(
            pair.id,
            oracle_response.price,
            oracle_response.last_updated_timestamp,
            publisher_name,
            source_name,
            0,
        )

    @staticmethod
    def from_dict(entry_dict: Any) -> "SpotEntry":
        base = dict(entry_dict["base"])
        return SpotEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            volume=entry_dict["volume"],
        )

    def __repr__(self) -> str:
        return (
            f'SpotEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}", volume={self.volume}))'
        )

    def __hash__(self) -> int:
        return hash((self.base, self.pair_id, self.price, self.volume))

    def to_proto_bytes(self) -> bytes:
        """Convert SpotEntry to protobuf bytes."""
        # Create protobuf PriceEntry message
        price_entry = entries_pb2.PriceEntry()

        # Set source
        price_entry.source = felt_to_str(self.base.source)

        # Set no chain (LMAX data is not chain-specific)
        price_entry.noChain = True

        # Set pair
        pair_id = felt_to_str(self.pair_id)
        if "/" in pair_id:
            base, quote = pair_id.split("/", 1)
        else:
            # For special instruments like SPX500m, use the full name as base
            base = pair_id
            quote = "USD"  # Default quote currency

        price_entry.pair.base = base
        price_entry.pair.quote = quote

        # Set timestamp (convert to milliseconds)
        price_entry.timestampMs = self.base.timestamp * 1000

        # Set price (convert to UInt128)
        price_entry.price.low = self.price & ((1 << 64) - 1)
        price_entry.price.high = (self.price >> 64) & ((1 << 64) - 1)

        # Set volume (convert to UInt128)
        price_entry.volume.low = self.volume & ((1 << 64) - 1)
        price_entry.volume.high = (self.volume >> 64) & ((1 << 64) - 1)

        # Set no expiration for spot entries
        price_entry.noExpiration = True

        return price_entry.SerializeToString()

    @classmethod
    def from_proto_bytes(cls, data: bytes) -> "SpotEntry":
        """Create SpotEntry from protobuf bytes."""
        price_entry = entries_pb2.PriceEntry()
        price_entry.ParseFromString(data)

        # Extract pair_id
        pair_id = f"{price_entry.pair.base}/{price_entry.pair.quote}"

        # Convert price from UInt128
        price = price_entry.price.low + (price_entry.price.high << 64)

        # Convert volume from UInt128
        volume = price_entry.volume.low + (price_entry.volume.high << 64)

        # Convert timestamp (from milliseconds to seconds)
        timestamp = price_entry.timestampMs // 1000

        return cls(
            pair_id=pair_id,
            price=price,
            timestamp=timestamp,
            source=price_entry.source,
            publisher="UNKNOWN",  # Publisher info not in protobuf
            volume=volume,
        )


class FutureEntry(Entry):
    """
    Represents a Future Entry.

    Also used to represent a Perp Entry - the only difference is that a perpetual future has no
    expiry timestamp.
    """

    base: BaseEntry
    pair_id: int
    price: int
    expiry_timestamp: int
    volume: int

    def __init__(
        self,
        pair_id: str | int,
        price: int,
        timestamp: int,
        source: str | int,
        publisher: str | int,
        expiry_timestamp: Optional[int] = None,
        volume: Optional[float | int] = None,
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
        if expiry_timestamp is None:
            expiry_timestamp = 0
        self.expiry_timestamp = expiry_timestamp

        if volume is None:
            volume = 0
        if isinstance(volume, float):
            volume = int(volume)
        self.volume = volume

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FutureEntry):
            return all(
                [
                    self.pair_id == other.pair_id,
                    self.price == other.price,
                    self.base.timestamp == other.base.timestamp,
                    self.base.source == other.base.source,
                    self.base.publisher == other.base.publisher,
                    self.expiry_timestamp == other.expiry_timestamp,
                    self.volume == other.volume,
                ]
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, tuple) and len(other) == 5:
            return all(
                [
                    self.pair_id == other[0],
                    self.price == other[1],
                    self.base == other[2],
                    self.expiry_timestamp == other[3],
                    self.volume == other[4],
                ]
            )
        return False

    def to_tuple(self) -> Tuple[int, int, int, int, int, int, int]:  # type: ignore[explicit-override, override]
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.expiry_timestamp,
            self.volume,
        )

    def serialize(self) -> Dict[str, object]:
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

    def offchain_serialize(self) -> Dict[str, object]:
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

    def __repr__(self) -> str:
        return (
            f'FutureEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, "
            f"timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}, '
            f"volume={self.volume}, "
            f'expiry_timestamp={self.expiry_timestamp})")'
        )

    def __hash__(self) -> int:
        return hash(
            (self.base, self.pair_id, self.price, self.expiry_timestamp, self.volume)
        )

    def get_timestamp(self) -> UnixTimestamp:
        return self.base.timestamp

    def get_expiry(self) -> Optional[str]:
        return datetime.utcfromtimestamp(self.expiry_timestamp).strftime(
            FUTURE_ENTRY_EXPIRIES_FORMAT
        )

    def get_pair_id(self) -> str:
        return felt_to_str(self.pair_id)

    def get_source(self) -> str:
        return felt_to_str(self.base.source)

    def get_asset_type(self) -> DataTypes:
        return DataTypes.FUTURE

    @staticmethod
    def from_dict(entry_dict: Any) -> "FutureEntry":
        base = dict(entry_dict["base"])
        return FutureEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            entry_dict["expiration_timestamp"],
            volume=entry_dict["volume"],
        )

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> Optional["FutureEntry"]:
        """
        Builds the object from a PragmaAsset and an OracleResponse.
        Method primarly used by our price pusher package when we're retrieving
        lastest oracle prices for comparisons with the latest prices of
        various APIs (binance etc).
        """
        if oracle_response.last_updated_timestamp == 0:
            return None

        return FutureEntry(
            pair.id,
            oracle_response.price,
            oracle_response.last_updated_timestamp,
            publisher_name,
            source_name,
            oracle_response.expiration_timestamp,
            0,
        )

    def to_proto_bytes(self) -> bytes:
        """Convert FutureEntry to protobuf bytes."""
        # Create protobuf PriceEntry message
        price_entry = entries_pb2.PriceEntry()

        # Set source
        price_entry.source = felt_to_str(self.base.source)

        # Set no chain (LMAX data is not chain-specific)
        price_entry.noChain = True

        # Set pair
        pair_id = felt_to_str(self.pair_id)
        if "/" in pair_id:
            base, quote = pair_id.split("/", 1)
        else:
            # For special instruments like SPX500m, use the full name as base
            base = pair_id
            quote = "USD"  # Default quote currency

        price_entry.pair.base = base
        price_entry.pair.quote = quote

        # Set timestamp (convert to milliseconds)
        price_entry.timestampMs = self.base.timestamp * 1000

        # Set price (convert to UInt128)
        price_entry.price.low = self.price & ((1 << 64) - 1)
        price_entry.price.high = (self.price >> 64) & ((1 << 64) - 1)

        # Set volume (convert to UInt128)
        price_entry.volume.low = self.volume & ((1 << 64) - 1)
        price_entry.volume.high = (self.volume >> 64) & ((1 << 64) - 1)

        # Set expiration timestamp if present
        if self.expiry_timestamp and self.expiry_timestamp > 0:
            price_entry.expirationTimestamp = self.expiry_timestamp * 1000
        else:
            price_entry.noExpiration = True

        return price_entry.SerializeToString()

    @classmethod
    def from_proto_bytes(cls, data: bytes) -> "FutureEntry":
        """Create FutureEntry from protobuf bytes."""
        price_entry = entries_pb2.PriceEntry()
        price_entry.ParseFromString(data)

        # Extract pair_id
        pair_id = f"{price_entry.pair.base}/{price_entry.pair.quote}"

        # Convert price from UInt128
        price = price_entry.price.low + (price_entry.price.high << 64)

        # Convert volume from UInt128
        volume = price_entry.volume.low + (price_entry.volume.high << 64)

        # Convert timestamp (from milliseconds to seconds)
        timestamp = price_entry.timestampMs // 1000

        # Extract expiry timestamp
        expiry_timestamp = None
        if price_entry.HasField("expirationTimestamp"):
            expiry_timestamp = price_entry.expirationTimestamp // 1000

        return cls(
            pair_id=pair_id,
            price=price,
            timestamp=timestamp,
            source=price_entry.source,
            publisher="UNKNOWN",  # Publisher info not in protobuf
            expiry_timestamp=expiry_timestamp,
            volume=volume,
        )


class GenericEntry(Entry):
    """
    Represents a Generic Entry.

    Currently used this way:
    instead of publishing all the future options for all availables instruments from Deribit,
    we place them in all a Merkle tree & we only publish the merkle root through this Generic entry.
    So the key will be DERIBIT_OPTIONS_MERKLE_ROOT and the value the merkle root containing
    all the price feeds.
    """

    base: BaseEntry
    key: int
    value: int

    def __init__(
        self,
        key: str | int,
        value: int,
        timestamp: int,
        source: str | int,
        publisher: str | int,
    ):
        if isinstance(key, str):
            key = str_to_felt(key)
        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)
        if isinstance(source, str):
            source = str_to_felt(source)

        self.key = key
        self.value = value
        self.base = BaseEntry(timestamp, source, publisher)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GenericEntry):
            return all(
                [
                    self.key == other.key,
                    self.value == other.value,
                    self.base.timestamp == other.base.timestamp,
                    self.base.source == other.base.source,
                    self.base.publisher == other.base.publisher,
                ]
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, tuple) and len(other) == 5:
            return all(
                [
                    self.key == other[0],
                    self.value == other[1],
                    self.base == other[2],
                ]
            )
        return False

    def to_tuple(self) -> Tuple[int, int, int, int, int]:  # type: ignore[explicit-override, override]
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.key,
            self.value,
        )

    def serialize(self) -> Dict[str, object]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": self.base.source,
                "publisher": self.base.publisher,
            },
            "key": self.key,
            "value": self.value,
        }

    def offchain_serialize(self) -> Dict[str, object]:
        serialized = {
            "base": {
                "timestamp": self.base.timestamp,
                "source": felt_to_str(self.base.source),
                "publisher": felt_to_str(self.base.publisher),
            },
            "key": felt_to_str(self.key),
            "value": self.value,
        }
        return serialized

    def __repr__(self) -> str:
        return (
            f'GenericEntry(key="{self.key}", '
            f'value="{self.value}", '
            f'timestamp="{self.base.timestamp}", '
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}")'
        )

    def __hash__(self) -> int:
        return hash((self.base, self.key, self.value))

    def get_timestamp(self) -> UnixTimestamp:
        return self.base.timestamp

    def get_expiry(self) -> Optional[str]:
        return None

    def get_pair_id(self) -> str:
        return felt_to_str(self.key)

    def get_source(self) -> str:
        return felt_to_str(self.base.source)

    def get_asset_type(self) -> DataTypes:
        return DataTypes.GENERIC

    @staticmethod
    def from_dict(entry_dict: Any) -> "GenericEntry":
        base = dict(entry_dict["base"])
        return GenericEntry(
            entry_dict["key"],
            entry_dict["value"],
            base["timestamp"],
            base["source"],
            base["publisher"],
        )

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> Optional["GenericEntry"]:
        """
        Builds the object from a PragmaAsset and an OracleResponse.
        Method primarly used by our price pusher package when we're retrieving
        lastest oracle prices for comparisons with the latest prices of
        various APIs (binance etc).
        """
        raise NotImplementedError(
            "😛 from_oracle_response does not exists for GenericEntry yet!"
        )


class OrderbookUpdateType(StrEnum):
    """Orderbook update type enum."""

    TARGET = "TARGET"
    DELTA = "DELTA"
    SNAPSHOT = "SNAPSHOT"


class InstrumentType(StrEnum):
    """Instrument type enum."""

    SPOT = "SPOT"
    PERP = "PERP"


@dataclass
class OrderbookData:
    """Orderbook data containing bids and asks."""

    update_id: int
    bids: List[Tuple[float, float]]  # List of (price, quantity) tuples
    asks: List[Tuple[float, float]]  # List of (price, quantity) tuples


class OrderbookEntry:
    """
    Represents an Orderbook Entry.
    """

    source: str
    instrument_type: InstrumentType
    pair: Pair
    type: OrderbookUpdateType
    data: OrderbookData
    timestamp_ms: int

    def __init__(
        self,
        source: str,
        instrument_type: InstrumentType | str,
        pair: Pair,
        type: OrderbookUpdateType | str,
        data: OrderbookData,
        timestamp_ms: int,
    ):
        self.source = source

        if isinstance(instrument_type, str):
            self.instrument_type = InstrumentType(instrument_type)

        self.pair = pair

        if isinstance(type, str):
            self.type = OrderbookUpdateType(type)

        self.data = data
        self.timestamp_ms = timestamp_ms

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OrderbookEntry):
            return all(
                [
                    self.source == other.source,
                    self.instrument_type == other.instrument_type,
                    self.pair == other.pair,
                    self.type == other.type,
                    self.data.update_id == other.data.update_id,
                    self.data.bids == other.data.bids,
                    self.data.asks == other.data.asks,
                    self.timestamp_ms == other.timestamp_ms,
                ]
            )
        return False

    def __repr__(self) -> str:
        return (
            f"OrderbookEntry(source='{self.source}', "
            f"instrument_type={self.instrument_type}, "
            f"pair={self.pair}, "
            f"type={self.type}, "
            f"update_id={self.data.update_id}, "
            f"bids_count={len(self.data.bids)}, "
            f"asks_count={len(self.data.asks)}, "
            f"timestamp_ms={self.timestamp_ms})"
        )

    def to_proto_bytes(self) -> bytes:
        """Convert OrderbookEntry to protobuf bytes."""
        # Create protobuf OrderbookEntry message
        orderbook_entry = entries_pb2.OrderbookEntry()

        # Set source
        orderbook_entry.source = self.source

        # Set instrument type
        if self.instrument_type == InstrumentType.SPOT:
            orderbook_entry.instrumentType = entries_pb2.InstrumentType.SPOT
        elif self.instrument_type == InstrumentType.PERP:
            orderbook_entry.instrumentType = entries_pb2.InstrumentType.PERP

        # Set pair
        orderbook_entry.pair.base = self.pair.base_currency.id
        orderbook_entry.pair.quote = self.pair.quote_currency.id

        # Set type using oneof field
        if self.type == OrderbookUpdateType.TARGET:
            orderbook_entry.type.update = entries_pb2.UpdateType.TARGET
        elif self.type == OrderbookUpdateType.DELTA:
            orderbook_entry.type.update = entries_pb2.UpdateType.DELTA
        elif self.type == OrderbookUpdateType.SNAPSHOT:
            orderbook_entry.type.snapshot = True

        # Set data
        orderbook_entry.data.update_id = self.data.update_id

        # Add bids
        for price, quantity in self.data.bids:
            bid = orderbook_entry.data.bids.add()
            bid.price = price
            bid.quantity = quantity

        # Add asks
        for price, quantity in self.data.asks:
            ask = orderbook_entry.data.asks.add()
            ask.price = price
            ask.quantity = quantity

        # Set timestamp
        orderbook_entry.timestampMs = self.timestamp_ms

        return orderbook_entry.SerializeToString()

    @classmethod
    def from_proto_bytes(cls, data: bytes) -> "OrderbookEntry":
        """Create OrderbookEntry from protobuf bytes."""
        orderbook_entry = entries_pb2.OrderbookEntry()
        orderbook_entry.ParseFromString(data)

        # Extract instrument type
        if orderbook_entry.instrumentType == entries_pb2.InstrumentType.SPOT:
            instrument_type = InstrumentType.SPOT
        elif orderbook_entry.instrumentType == entries_pb2.InstrumentType.PERP:
            instrument_type = InstrumentType.PERP
        else:
            raise ValueError(
                f"Unknown instrument type: {orderbook_entry.instrumentType}"
            )

        # Extract pair
        pair = Pair.from_tickers(orderbook_entry.pair.base, orderbook_entry.pair.quote)

        # Extract type from oneof field
        if orderbook_entry.type.HasField("update"):
            if orderbook_entry.type.update == entries_pb2.UpdateType.TARGET:
                type_ = OrderbookUpdateType.TARGET
            elif orderbook_entry.type.update == entries_pb2.UpdateType.DELTA:
                type_ = OrderbookUpdateType.DELTA
            else:
                raise ValueError(f"Unknown update type: {orderbook_entry.type.update}")
        elif orderbook_entry.type.HasField("snapshot"):
            type_ = OrderbookUpdateType.SNAPSHOT
        else:
            raise ValueError(f"Unknown orderbook update type: {orderbook_entry.type}")

        # Extract orderbook data
        bids = [(bid.price, bid.quantity) for bid in orderbook_entry.data.bids]
        asks = [(ask.price, ask.quantity) for ask in orderbook_entry.data.asks]

        data = OrderbookData(
            update_id=orderbook_entry.data.update_id, bids=bids, asks=asks
        )

        return cls(
            source=orderbook_entry.source,
            instrument_type=instrument_type,
            pair=pair,
            type=type_,
            data=data,
            timestamp_ms=orderbook_entry.timestampMs,
        )
