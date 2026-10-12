from unittest.mock import AsyncMock, MagicMock

import pytest

from price_pusher.core.pusher import PricePusher


def _entry(pair_id: str, price: int, timestamp: int):
    entry = MagicMock()
    entry.get_pair_id.return_value = pair_id
    entry.price = price
    entry.base.timestamp = timestamp
    return entry


@pytest.mark.asyncio
async def test_miden_entry_carries_the_number_of_aggregated_sources():
    miden_client = MagicMock()
    miden_client.publish_entries = AsyncMock(return_value=[True, True])
    pusher = PricePusher(MagicMock(), miden_client=miden_client)

    await pusher.publish_to_miden(
        [
            _entry("BTC/USD", 100, 10),
            _entry("BTC/USD", 300, 12),
            _entry("BTC/USD", 200, 11),
            _entry("ETH/USD", 50, 10),
            _entry("ETH/USD", 70, 10),
        ]
    )

    published = {e.pair: e for e in miden_client.publish_entries.call_args.args[0]}
    assert (published["1:0"].price, published["1:0"].num_sources) == (200, 3)
    assert (published["2:0"].price, published["2:0"].num_sources) == (60, 2)
