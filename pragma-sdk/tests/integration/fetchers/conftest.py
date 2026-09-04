"""
Fetcher tests must never reach real reference venues: the off-chain
ReferencePriceProvider is replaced by a deterministic stub for every test in
this directory (stables at 1.0, ETH 2500, BTC 80000).
"""

import pytest

from unittest import mock

from pragma_sdk.common.fetchers.handlers.reference_price import ReferencePriceError


class StubReferenceProvider:
    PRICES = {
        "USDT": 1.0,
        "USDC": 1.0,
        "DAI": 1.0,
        "USD": 1.0,
        "USDPLUS": 1.0,
        "ETH": 2500.0,
        "BTC": 80000.0,
    }

    def __init__(self):
        self.calls = []

    async def get_price(self, base, quote="USD", session=None):
        self.calls.append((base, quote))
        try:
            return self.PRICES[base] / self.PRICES[quote]
        except KeyError as e:
            raise ReferencePriceError(f"no stub reference for {e}") from e


@pytest.fixture(autouse=True)
def stub_reference_provider():
    stub = StubReferenceProvider()
    with mock.patch(
        "pragma_sdk.common.fetchers.handlers.reference_price._default_provider", stub
    ):
        yield stub
