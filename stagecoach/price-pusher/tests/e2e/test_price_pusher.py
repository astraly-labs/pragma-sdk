import pytest
import sqlite3
import tempfile
import subprocess
import yaml
import asyncio
import signal
from unittest.mock import patch, AsyncMock


# Fixture to set up an SQLite database
@pytest.fixture
def sqlite_db():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE prices (
            pair_id TEXT,
            price REAL,
            timestamp INTEGER,
            decimals INTEGER
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.skip(reason="IN PROGRESS.")
@pytest.mark.asyncio
async def test_main_e2e(sqlite_db):
    # Create a temporary config.yaml file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w") as temp_config:
        config_data = [
            {
                "pairs": {"spot": ["BTC/USD"], "future": ["BTC/USD"]},
                "time_difference": 60,
                "price_deviation": 0.5,
            }
        ]
        yaml.dump(config_data, temp_config)
        config_path = temp_config.name

    # Mock the fetchers and oracle data
    with (
        patch(
            "price_pusher.core.poller.PricePoller._fetch_action", new_callable=AsyncMock
        ) as mock_fetch_action,
        patch(
            "price_pusher.core.listener.PriceListener._fetch_all_oracle_prices",
            new_callable=AsyncMock,
        ) as mock_fetch_oracle_prices,
    ):
        # Mock fetcher data
        mock_fetch_action.return_value = [
            {"pair_id": "BTC/USD", "price": 10000, "timestamp": 1234567890, "decimals": 8}
        ]

        # Mock oracle data
        mock_fetch_oracle_prices.return_value = [
            {"pair_id": "BTC/USD", "price": 10000, "timestamp": 1234567890, "decimals": 8}
        ]

        # Run the CLI command in a subprocess
        process = subprocess.Popen(
            [
                "python",
                "-m",
                "price_pusher.main",
                "--config-file",
                config_path,
                "--target",
                "offchain",
                "--network",
                "mainnet",
                "--private-key",
                "plain:0x06a2e725e8ada061d480e10c8c586e8607b599f577b34f5132fd7b314dbf2451",
                "--publisher-name",
                "test_publisher",
                "--publisher-address",
                "0x123",
                "--api-base-url",
                "https://api.pragma.is.mocked",
                "--api-key",
                "test_api_key",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Allow the process to run for a short time (e.g., 5 seconds)
        await asyncio.sleep(15)

        # Terminate the process
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate()

        # Check if the command was successful
        assert process.returncode == 0, f"CLI command failed with output: {stdout} {stderr}"

        # Verify data insertion in SQLite database
        cursor = sqlite_db.cursor()
        cursor.execute("SELECT * FROM prices WHERE pair_id = 'BTC/USD'")
        result = cursor.fetchone()
        assert result == ("BTC/USD", 10000, 1234567890, 8)
