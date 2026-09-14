"""
The VRF contract's callback_fee_limit is in wei; v3 estimates are in FRI (#328).
"""

from unittest.mock import AsyncMock

import pytest
from starknet_py.net.client_models import EstimatedFee, PriceUnit

from pragma_sdk.onchain.mixins.randomness import RandomnessMixin


class _Spot:
    def __init__(self, price: int, decimals: int):
        self.price, self.decimals = price, decimals


def _estimate(fee: int, unit: PriceUnit) -> EstimatedFee:
    return EstimatedFee(
        l1_gas_consumed=0,
        l1_gas_price=1,
        l2_gas_consumed=fee,
        l2_gas_price=1,
        l1_data_gas_consumed=0,
        l1_data_gas_price=1,
        overall_fee=fee,
        unit=unit,
    )


def _mixin(strk_usd: float, eth_usd: float) -> RandomnessMixin:
    m = RandomnessMixin()
    m.get_spot = AsyncMock(  # type: ignore[attr-defined]
        side_effect=lambda pair: _Spot(
            int((strk_usd if pair == "STRK/USD" else eth_usd) * 10**8), 8
        )
    )
    return m


@pytest.mark.asyncio
async def test_fri_estimate_is_converted_with_oracle_prices():
    # 1 STRK = $0.03, 1 ETH = $3000 -> 1e18 FRI = 1e13 wei
    m = _mixin(0.03, 3000.0)
    assert await m._fee_in_wei(_estimate(10**18, PriceUnit.FRI)) == 10**13


@pytest.mark.asyncio
async def test_wei_estimate_is_returned_as_is():
    m = _mixin(0.03, 3000.0)
    assert await m._fee_in_wei(_estimate(12345, PriceUnit.WEI)) == 12345
    m.get_spot.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_zero_oracle_price_refuses_to_convert():
    m = _mixin(0.0, 3000.0)
    with pytest.raises(ValueError):
        await m._fee_in_wei(_estimate(10**18, PriceUnit.FRI))
