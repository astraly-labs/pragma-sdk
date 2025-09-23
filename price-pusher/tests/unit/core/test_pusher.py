import pytest
import logging

from typing import List
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pragma_sdk.common.types.entry import Entry
from price_pusher.core.pusher import PricePusher


@pytest.mark.asyncio
async def test_update_price_feeds_success(caplog):
    caplog.set_level(logging.INFO)

    mock_client = SimpleNamespace()
    mock_entry = MagicMock()
    mock_response = [mock_entry]
    mock_client.publish_many = AsyncMock(return_value=mock_response)

    price_pusher = PricePusher(mock_client)
    price_pusher.wait_for_publishing_acceptance = AsyncMock()
    entries: List[MagicMock] = [mock_entry]
    response = await price_pusher.update_price_feeds(entries)

    assert response == mock_response
    mock_client.publish_many.assert_awaited_once_with(entries)
    price_pusher.wait_for_publishing_acceptance.assert_awaited_once_with(mock_response)

    assert any(
        f"processing {len(entries)} new asset(s) to push..." in record.message
        for record in caplog.records
    )
    assert any(
        f"Successfully published {len(entries)} entrie(s)" in record.message
        for record in caplog.records
    )
    assert price_pusher.consecutive_push_error == 0
    assert price_pusher.is_publishing_on_chain


@pytest.mark.asyncio
async def test_update_price_feeds_failure(caplog):
    caplog.set_level(logging.INFO)
    mock_entry = MagicMock(spec=Entry)

    mock_client = SimpleNamespace()
    mock_client.publish_many = AsyncMock(side_effect=Exception("Test Exception"))

    price_pusher = PricePusher(mock_client)
    price_pusher.wait_for_publishing_acceptance = AsyncMock()

    entries = [mock_entry]

    response = await price_pusher.update_price_feeds(entries)

    assert response is None
    mock_client.publish_many.assert_awaited_once_with(entries)
    price_pusher.wait_for_publishing_acceptance.assert_not_awaited()

    assert any(
        "processing 1 new asset(s) to push..." in record.message
        for record in caplog.records
    )
    assert any(
        "could not publish entrie(s): Test Exception" in record.message
        for record in caplog.records
    )
    assert price_pusher.consecutive_push_error == 1
