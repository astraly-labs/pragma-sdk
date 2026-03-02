"""Tests for protobuf serialization/deserialization of entry types.

This test suite focuses on the OrderbookEntry protobuf functionality,
which includes comprehensive testing of the new OrderbookUpdateType structure
with TARGET, DELTA, and SNAPSHOT variants matching the Rust implementation.
"""

from pragma_sdk.common.types.entry import (
    OrderbookEntry,
    OrderbookData,
    OrderbookUpdateType,
    InstrumentType,
)
from pragma_sdk.common.types.pair import Pair


class TestOrderbookEntryProtobuf:
    """Test protobuf serialization/deserialization for OrderbookEntry."""

    def test_orderbook_entry_target_proto(self):
        """Test OrderbookEntry with TARGET update type."""
        pair = Pair.from_tickers("BTC", "USD")
        data = OrderbookData(
            update_id=4242,
            bids=[(42000.0, 1.0), (41999.0, 0.5)],
            asks=[(42001.0, 1.5), (42002.0, 2.0)],
        )

        entry = OrderbookEntry(
            source="TEST",
            instrument_type=InstrumentType.SPOT,
            pair=pair,
            type=OrderbookUpdateType.TARGET,
            data=data,
            timestamp_ms=145567,
        )

        proto_bytes = entry.to_proto_bytes()
        deserialized_entry = OrderbookEntry.from_proto_bytes(proto_bytes)

        assert deserialized_entry == entry

    def test_orderbook_entry_delta_proto(self):
        """Test OrderbookEntry with DELTA update type."""
        pair = Pair.from_tickers("BTC", "USD")
        data = OrderbookData(
            update_id=4242,
            bids=[(0.0, 1.0), (42.00, 1.0)],
            asks=[(42.00, 69.00), (1.00, 42.00)],
        )

        entry = OrderbookEntry(
            source="TEST",
            instrument_type=InstrumentType.SPOT,
            pair=pair,
            type=OrderbookUpdateType.DELTA,
            data=data,
            timestamp_ms=145567,
        )

        proto_bytes = entry.to_proto_bytes()
        deserialized_entry = OrderbookEntry.from_proto_bytes(proto_bytes)

        assert deserialized_entry == entry

    def test_orderbook_entry_snapshot_proto(self):
        """Test OrderbookEntry with SNAPSHOT update type."""
        pair = Pair.from_tickers("BTC", "USD")
        data = OrderbookData(
            update_id=4242,
            bids=[(0.0, 1.0), (42.00, 1.0)],
            asks=[(42.00, 69.00), (1.00, 42.00)],
        )

        entry = OrderbookEntry(
            source="TEST",
            instrument_type=InstrumentType.SPOT,
            pair=pair,
            type=OrderbookUpdateType.SNAPSHOT,
            data=data,
            timestamp_ms=145567,
        )

        proto_bytes = entry.to_proto_bytes()
        deserialized_entry = OrderbookEntry.from_proto_bytes(proto_bytes)

        assert deserialized_entry == entry

    def test_orderbook_entry_perp_instrument(self):
        """Test OrderbookEntry with PERP instrument type."""
        pair = Pair.from_tickers("ETH", "USD")
        data = OrderbookData(
            update_id=5555,
            bids=[(3000.0, 2.0), (2999.0, 1.5)],
            asks=[(3001.0, 2.5), (3002.0, 3.0)],
        )

        entry = OrderbookEntry(
            source="BINANCE",
            instrument_type=InstrumentType.PERP,
            pair=pair,
            type=OrderbookUpdateType.TARGET,
            data=data,
            timestamp_ms=1654321,
        )

        proto_bytes = entry.to_proto_bytes()
        deserialized_entry = OrderbookEntry.from_proto_bytes(proto_bytes)

        assert deserialized_entry == entry

    def test_orderbook_entry_empty_bids_asks(self):
        """Test OrderbookEntry with empty bids and asks."""
        pair = Pair.from_tickers("SOL", "USD")
        data = OrderbookData(update_id=1111, bids=[], asks=[])

        entry = OrderbookEntry(
            source="EMPTY_TEST",
            instrument_type=InstrumentType.SPOT,
            pair=pair,
            type=OrderbookUpdateType.SNAPSHOT,
            data=data,
            timestamp_ms=987654,
        )

        proto_bytes = entry.to_proto_bytes()
        deserialized_entry = OrderbookEntry.from_proto_bytes(proto_bytes)

        assert deserialized_entry == entry


class TestOrderbookUpdateTypeValues:
    """Test OrderbookUpdateType enum values."""

    def test_orderbook_update_type_values(self):
        """Test that OrderbookUpdateType has the correct values."""
        assert OrderbookUpdateType.TARGET == "TARGET"
        assert OrderbookUpdateType.DELTA == "DELTA"
        assert OrderbookUpdateType.SNAPSHOT == "SNAPSHOT"

        # Test that all values are covered
        all_values = list(OrderbookUpdateType)
        assert len(all_values) == 3
        assert OrderbookUpdateType.TARGET in all_values
        assert OrderbookUpdateType.DELTA in all_values
        assert OrderbookUpdateType.SNAPSHOT in all_values
