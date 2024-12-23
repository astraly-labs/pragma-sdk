import pytest
import logging

from typing import List
from unittest.mock import AsyncMock, MagicMock
from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry
from price_pusher.core.pusher import PricePusher


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=PragmaClient)
    return client


@pytest.fixture
def price_pusher(mock_client):
    return PricePusher(client=mock_client)


@pytest.mark.asyncio
async def test_update_price_feeds_success(caplog):
    caplog.set_level(logging.INFO)

    mock_client = AsyncMock()
    mock_entry = MagicMock()
    mock_response = [mock_entry]
    mock_client.publish_entries.return_value = mock_response

    price_pusher = PricePusher(mock_client)
    entries: List[MagicMock] = [mock_entry]
    response = await price_pusher.update_price_feeds(entries)

    assert response == mock_response
    mock_client.publish_entries.assert_called_once_with(entries)

    assert any(
        f"processing {len(entries)} new asset(s) to push..." in record.message
        for record in caplog.records
    )
    assert any(
        f"Successfully published {len(entries)} entrie(s)" in record.message
        for record in caplog.records
    )
    assert price_pusher.consecutive_push_error == 0
    assert not price_pusher.is_publishing_on_chain


@pytest.mark.asyncio
async def test_update_price_feeds_failure(price_pusher, mock_client, caplog):
    caplog.set_level(logging.INFO)
    mock_entry = MagicMock(spec=Entry)
    mock_client.publish_entries.side_effect = Exception("Test Exception")

    entries = [mock_entry]

    response = await price_pusher.update_price_feeds(entries)

    assert response is None
    mock_client.publish_entries.assert_called_once_with(entries)

    assert any(
        "processing 1 new asset(s) to push..." in record.message
        for record in caplog.records
    )
    assert any(
        "could not publish entrie(s): Test Exception" in record.message
        for record in caplog.records
    )
