import pytest
from typing import Tuple
from unittest.mock import Mock, AsyncMock
from nostra_lp_pricer.pricing.calculator import PoolPriceCalculator
# Constants
TARGET_DECIMALS = 18  

class MockERC20:
    def __init__(self, address: int, decimals: int):
        self.address = address
        self.decimals = decimals

class MockReserves(tuple):
    def __new__(cls, reserve0: int, reserve1: int):
        return super(MockReserves, cls).__new__(cls, (reserve0, reserve1))

@pytest.fixture
def mock_pool():
    pool = Mock()
    pool.network = "sepolia"
    return pool

@pytest.fixture
def mock_oracle():
    oracle = Mock()
    oracle.get_token_price_and_decimals = AsyncMock()
    return oracle

@pytest.fixture
def calculator(mock_pool, mock_oracle):
    return PoolPriceCalculator(mock_pool, mock_oracle)

@pytest.mark.asyncio
async def test_compute_lp_price_same_decimals(calculator, mock_pool, mock_oracle):
    # Setup
    tokens = (1, 2)  # Token addresses
    reserves = MockReserves(1000 * 10**18, 2000 * 10**18)  # Both tokens with 18 decimals
    total_supply = 1500 * 10**18
    
    # Mock token contracts
    token0 = MockERC20(tokens[0], 18)
    token1 = MockERC20(tokens[1], 18)
    
    # Mock get_contract function
    global get_contract
    get_contract = Mock(side_effect=[token0, token1])
    
    # Mock oracle responses
    mock_oracle.get_token_price_and_decimals.side_effect = [
        (2 * 10**18, 18),  # Token0 price: $2 with 18 decimals
        (1 * 10**18, 18)   # Token1 price: $1 with 18 decimals
    ]
    
    # Calculate expected price
    # (1000 * 10^18 * 2 + 2000 * 10^18 * 1) / (1500 * 10^18)
    expected_price = (1000 * 2 + 2000 * 1) * 10**18 // 1500
    
    # Execute
    result = await calculator.compute_lp_price(tokens, reserves, total_supply)
    
    # Verify
    assert result == expected_price

@pytest.mark.asyncio
async def test_compute_lp_price_different_decimals(calculator, mock_pool, mock_oracle):
    # Setup
    tokens = (1, 2)
    reserves = MockReserves(1000 * 10**6, 2000 * 10**18)  # Token0: 6 decimals, Token1: 18 decimals
    total_supply = 1500 * 10**18
    
    token0 = MockERC20(tokens[0], 6)
    token1 = MockERC20(tokens[1], 18)
    
    global get_contract
    get_contract = Mock(side_effect=[token0, token1])
    
    mock_oracle.get_token_price_and_decimals.side_effect = [
        (2 * 10**6, 6),    # Token0 price: $2 with 6 decimals
        (1 * 10**18, 18)   # Token1 price: $1 with 18 decimals
    ]
    
    # Calculate expected price with decimal adjustments
    token0_price_adjusted = 2 * 10**18  # Adjusted from 6 to 18 decimals
    token1_price = 1 * 10**18
    expected_price = (1000 * 10**6 * token0_price_adjusted + 2000 * 10**18 * token1_price) // (1500 * 10**18)
    
    # Execute
    result = await calculator.compute_lp_price(tokens, reserves, total_supply)
    
    # Verify
    assert result == expected_price

@pytest.mark.asyncio
async def test_compute_lp_price_higher_decimals(calculator, mock_pool, mock_oracle):
    # Setup
    tokens = (1, 2)
    reserves = MockReserves(1000 * 10**20, 2000 * 10**18)  # Token0: 20 decimals, Token1: 18 decimals
    total_supply = 1500 * 10**18
    
    token0 = MockERC20(tokens[0], 20)
    token1 = MockERC20(tokens[1], 18)
    
    global get_contract
    get_contract = Mock(side_effect=[token0, token1])
    
    mock_oracle.get_token_price_and_decimals.side_effect = [
        (2 * 10**20, 20),  # Token0 price: $2 with 20 decimals
        (1 * 10**18, 18)   # Token1 price: $1 with 18 decimals
    ]
    
    # Calculate expected price with decimal adjustments
    token0_price_adjusted = 2 * 10**18  # Adjusted from 20 to 18 decimals
    token1_price = 1 * 10**18
    expected_price = (1000 * 10**20 * token0_price_adjusted + 2000 * 10**18 * token1_price) // (1500 * 10**18)
    
    # Execute
    result = await calculator.compute_lp_price(tokens, reserves, total_supply)
    
    # Verify
    assert result == expected_price

@pytest.mark.asyncio
async def test_compute_lp_price_zero_supply(calculator, mock_pool, mock_oracle):
    # Setup
    tokens = (1, 2)
    reserves = MockReserves(1000 * 10**18, 2000 * 10**18)
    total_supply = 0
    
    token0 = MockERC20(tokens[0], 18)
    token1 = MockERC20(tokens[1], 18)
    
    global get_contract
    get_contract = Mock(side_effect=[token0, token1])
    
    mock_oracle.get_token_price_and_decimals.side_effect = [
        (2 * 10**18, 18),
        (1 * 10**18, 18)
    ]
    
    # Execute & Verify
    with pytest.raises(ZeroDivisionError):
        await calculator.compute_lp_price(tokens, reserves, total_supply)