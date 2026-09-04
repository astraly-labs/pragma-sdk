import pytest

from unittest import mock

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.types.entry import SpotEntry

from tests.integration.fixtures.fetchers import get_mock_data
from tests.integration.constants import (
    ONCHAIN_SAMPLE_PAIRS,
    STABLE_MOCK_PRICE,
)
from tests.integration.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from tests.integration.utils import are_entries_list_equal

# Response of the Price Fetcher for the quote-liquidity check (one base, status
# PRICE_AVAILABLE, any u256 price): the fetcher only looks at the status.
QUOTE_LIQUIDITY_OK = [1, 3, 165743466482862031119997495940211490227, 666]
QUOTE_LIQUIDITY_INSUFFICIENT = [1, 1]


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_rpc_fetcher(rpc_fetcher_config):
    mock_data = get_mock_data(rpc_fetcher_config)
    fetcher = rpc_fetcher_config["fetcher_class"](ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME)

    with (
        mock.patch.object(
            fetcher.client,
            "get_spot",
            return_value=STABLE_MOCK_PRICE,
        ) as get_spot,
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            side_effect=[QUOTE_LIQUIDITY_OK, *mock_data.values()],
        ),
    ):
        result = await fetcher.fetch(session=mock.MagicMock())
        assert are_entries_list_equal(result, rpc_fetcher_config["expected_result"])
        # USD hops are rebased at a fixed 1.0: the on-chain stable price must
        # never be read, so a poisoned median cannot leak into Ekubo entries.
        assert get_spot.call_count == 0


# NOTE: This test work because we only have Ekubo as Rpc Fetcher for now.
# NOTE: If you just added a new fetcher here and this fail, adapt/remove this test.
@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_publisher_error_async_rpc_fetcher(rpc_fetcher_config):
    pairs = [Pair.from_tickers("SOL", "USD")]
    fetcher = rpc_fetcher_config["fetcher_class"](pairs, PUBLISHER_NAME)

    with (
        mock.patch.object(
            fetcher.client,
            "get_spot",
            return_value=STABLE_MOCK_PRICE,
        ),
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            side_effect=[QUOTE_LIQUIDITY_OK, [1, 0]],
        ),
    ):
        result = await fetcher.fetch(session=mock.MagicMock())
        expected = [
            PublisherFetchError("Price feed not initialized for SOL/USDC in Ekubo")
        ]
        assert result == expected


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_quote_without_liquidity_rejects_all_pairs(rpc_fetcher_config):
    """
    Regression for the USDC.e incident: when the quote token's oracle pool has
    no liquidity, the Price Fetcher still answers with a frozen price for every
    base. We must refuse the whole quote group and never call get_prices for it.
    """
    fetcher = rpc_fetcher_config["fetcher_class"](ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME)

    with (
        mock.patch.object(
            fetcher.client,
            "get_spot",
            return_value=STABLE_MOCK_PRICE,
        ),
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            side_effect=[QUOTE_LIQUIDITY_INSUFFICIENT],
        ) as call_contract,
    ):
        result = await fetcher.fetch(session=mock.MagicMock())

    assert call_contract.call_count == 1
    assert len(result) == len(ONCHAIN_SAMPLE_PAIRS)
    for pair, error in zip(ONCHAIN_SAMPLE_PAIRS, result):
        assert isinstance(error, PublisherFetchError)
        assert str(pair) in str(error)
        assert "USDC" in str(error)
        assert "liquidity" in str(error).lower()


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_hop_back_uses_each_pairs_own_quote(rpc_fetcher_config):
    """
    Regression: the hop-back quote was taken from self.pairs[0]. With the
    mainnet config (WBTC/BTC next to X/USD pairs) the whole fetcher failed
    with "No valid hop price found for USDC/BTC" whenever a BTC-quoted pair
    came first. Each pair must be rebased to its own requested quote.
    """
    pairs = [Pair.from_tickers("WBTC", "BTC"), Pair.from_tickers("LUSD", "USD")]
    fetcher = rpc_fetcher_config["fetcher_class"](pairs, PUBLISHER_NAME)
    lusd_response = get_mock_data(rpc_fetcher_config)["LUSD"][:4]  # one price

    with (
        mock.patch.object(fetcher.client, "get_spot", return_value=STABLE_MOCK_PRICE),
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            side_effect=[QUOTE_LIQUIDITY_OK, [1, *lusd_response[1:]]],
        ),
    ):
        result = await fetcher.fetch(session=mock.MagicMock())

    by_type = {type(r): r for r in result}
    assert "WBTC/BTC" in str(
        by_type[PublisherFetchError]
    )  # BTC has no Starknet address
    assert by_type[SpotEntry].pair_id == Pair.from_tickers("LUSD", "USD").id


def test_zero_price_entries_are_rejected():
    from pragma_sdk.common.fetchers.fetcher_client import FetcherClient

    dead = SpotEntry("DAI/USD", 0, 12345, "BINANCE", PUBLISHER_NAME)
    live = SpotEntry("DAI/USD", 99990000, 12345, "BITSTAMP", PUBLISHER_NAME)
    assert FetcherClient._reject_zero_price(live) is live
    rejected = FetcherClient._reject_zero_price(dead)
    assert isinstance(rejected, PublisherFetchError)
    assert "BINANCE" in str(rejected)
