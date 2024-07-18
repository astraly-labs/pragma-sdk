import time
import pytest
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.fetchers.handlers.index_aggregator_handler import (
    AssetQuantities,
    IndexAggregatorHandler,
)


def create_mock_currency(id: str, decimals: int) -> Currency:
    return Currency(currency_id=id, decimals=decimals, is_abstract_currency=False)


def create_mock_pair(base: str, quote: str, decimals: int) -> Pair:
    base_currency = create_mock_currency(base, decimals)
    quote_currency = create_mock_currency(quote, decimals)
    return Pair(base_currency, quote_currency)


def create_mock_spot_entry(pair: Pair, price: int, volume: int = 0) -> SpotEntry:
    return SpotEntry(
        pair_id=pair.id,
        price=price,
        timestamp=int(time.time()),
        source="test_source",
        publisher="test_publisher",
        volume=volume,
    )


def create_mock_asset_quantities(pair: Pair, quantities: float) -> AssetQuantities:
    return AssetQuantities(pair, quantities)


@pytest.fixture
def sample_data():
    pairs = [
        create_mock_pair("ETH", "USD", 2),
        create_mock_pair("BTC", "USD", 3),
        create_mock_pair("XRP", "USD", 4),
    ]
    spot_entries = [
        create_mock_spot_entry(pairs[0], 10000, 10),
        create_mock_spot_entry(pairs[1], 20000, 20),
        create_mock_spot_entry(pairs[2], 30000, 30),
    ]
    pair_quantities = [
        create_mock_asset_quantities(pairs[0], 0.1),
        create_mock_asset_quantities(pairs[1], 0.2),
        create_mock_asset_quantities(pairs[2], 0.7),
    ]
    return spot_entries, pair_quantities


def test_index_aggregation_initialization(sample_data):
    spot_entries, pair_quantities = sample_data
    index_agg = IndexAggregatorHandler(spot_entries, pair_quantities)

    assert len(index_agg.spot_entries) == 3
    assert len(index_agg.pair_quantities) == 3


def test_get_index_value(sample_data):
    spot_entries, pair_quantities = sample_data
    index_agg = IndexAggregatorHandler(spot_entries, pair_quantities)

    expected_value = 1000000 * 0.1 + 200000 * 0.2 + 30000 * 0.7
    assert index_agg.get_index_value() == expected_value


def test_standardize_decimals(sample_data):
    spot_entries, pair_quantities = sample_data
    index_agg = IndexAggregatorHandler(spot_entries, pair_quantities)

    index_agg.standardize_decimals()

    assert index_agg.spot_entries[0].price == 1000000
    assert index_agg.spot_entries[0].volume == 1000
    assert index_agg.spot_entries[1].price == 200000
    assert index_agg.spot_entries[1].volume == 200
    assert index_agg.spot_entries[2].price == 30000
    assert index_agg.spot_entries[2].volume == 30


@pytest.mark.parametrize(
    "spot_entries,pair_quantities,expected",
    [
        (
            [create_mock_spot_entry(create_mock_pair("ETH", "USD", 2), 10000)],
            [create_mock_asset_quantities(create_mock_pair("ETH", "USD", 2), 1)],
            10000,
        ),
        (
            [
                create_mock_spot_entry(create_mock_pair("ETH", "USD", 2), 10000),
                create_mock_spot_entry(create_mock_pair("BTC", "USD", 3), 20000),
            ],
            [
                create_mock_asset_quantities(create_mock_pair("ETH", "USD", 2), 0.5),
                create_mock_asset_quantities(create_mock_pair("BTC", "USD", 3), 0.5),
            ],
            60000,
        ),
    ],
)
def test_get_index_value_parametrized(spot_entries, pair_quantities, expected):
    index_agg = IndexAggregatorHandler(spot_entries, pair_quantities)
    assert index_agg.get_index_value() == expected
