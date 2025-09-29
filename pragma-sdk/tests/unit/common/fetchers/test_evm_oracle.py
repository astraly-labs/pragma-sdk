import pytest
from time import monotonic

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    FeedConfig,
)
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler


class DummyEVMFetcher(EVMOracleFeedFetcher):
    """Minimal concrete fetcher for testing the base EVM oracle logic."""

    SOURCE = "TEST_EVM"

    def __init__(self, rpc_urls):
        # Bypass abstract parent initialisation that requires a network client
        self._rpc_urls = list(dict.fromkeys(rpc_urls))
        if not self._rpc_urls:
            raise ValueError("rpc_urls must not be empty")
        self._rpc_index = 0
        self._rpc_failures = {}
        self._request_id = 0
        self.publisher = "TEST"
        self.pairs = []
        self.hop_handler = HopHandler()
        self.feed_configs = {"BTC/USD": FeedConfig(contract_address="0x1", decimals=0)}


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class FakeContextManager:
    def __init__(self, outcome):
        self._outcome = outcome

    async def __aenter__(self):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return FakeResponse(self._outcome["status"], self._outcome["payload"])

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, responses):
        # Copy queues so tests can reuse the original data structures safely
        self._responses = {url: list(queue) for url, queue in responses.items()}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(url)
        queue = self._responses.get(url)
        if queue is None or not queue:
            raise AssertionError(f"No queued response for {url}")
        outcome = queue.pop(0)
        return FakeContextManager(outcome)


@pytest.mark.asyncio
async def test_rotates_rpc_after_failure():
    fetcher = DummyEVMFetcher(["https://rpc-1", "https://rpc-2"])
    config = FeedConfig(contract_address="0x123", decimals=0)
    session = FakeSession(
        {
            "https://rpc-1": [{"status": 500, "payload": {}}],
            "https://rpc-2": [{"status": 200, "payload": {"result": "0x2"}}],
        }
    )

    value = await fetcher._read_feed_value(session, config)

    assert value == 2.0
    assert session.calls == ["https://rpc-1", "https://rpc-2"]
    assert "https://rpc-1" in fetcher._rpc_failures
    assert "https://rpc-2" not in fetcher._rpc_failures


@pytest.mark.asyncio
async def test_skips_rpc_in_cooldown():
    fetcher = DummyEVMFetcher(["https://rpc-1", "https://rpc-2"])
    config = FeedConfig(contract_address="0x123", decimals=0)
    fetcher._rpc_failures["https://rpc-1"] = monotonic()

    session = FakeSession(
        {
            "https://rpc-2": [{"status": 200, "payload": {"result": "0x3"}}],
        }
    )

    value = await fetcher._read_feed_value(session, config)

    assert value == 3.0
    assert session.calls == ["https://rpc-2"]


@pytest.mark.asyncio
async def test_retry_rpc_after_cooldown_expired():
    fetcher = DummyEVMFetcher(["https://rpc-1", "https://rpc-2"])
    config = FeedConfig(contract_address="0x123", decimals=0)
    fetcher._rpc_failures["https://rpc-1"] = (
        monotonic() - fetcher.RPC_FAILURE_COOLDOWN_SECONDS - 1
    )

    session = FakeSession(
        {
            "https://rpc-1": [{"status": 200, "payload": {"result": "0x5"}}],
        }
    )

    value = await fetcher._read_feed_value(session, config)

    assert value == 5.0
    assert session.calls == ["https://rpc-1"]
    assert "https://rpc-1" not in fetcher._rpc_failures
