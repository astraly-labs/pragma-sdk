import asyncio
import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pragma_sdk.miden.client import (
    PragmaMidenClient,
    MidenEntry,
    STARKNET_PAIR_TO_MIDEN_FAUCET,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_starknet_entry(pair_id: str, price: int):
    """Build a minimal mock Starknet SpotEntry."""
    entry = MagicMock()
    entry.get_pair_id.return_value = pair_id
    entry.price = price
    entry.base = MagicMock()
    entry.base.timestamp = int(time.time())
    return entry


def write_config(tmp_path: Path, network: str = "testnet") -> Path:
    """Write a minimal pragma_miden.json and return its path."""
    config = {
        "networks": {
            network: {
                "oracle_account_id": "0xafebd403be621e005bf03b9fec7fe8",
                "publisher_account_ids": ["0x474d7a81bb950b001661523cdd7c0b"],
            }
        }
    }
    config_path = tmp_path / "pragma_miden.json"
    config_path.write_text(json.dumps(config))
    return config_path


# ---------------------------------------------------------------------------
# MidenEntry.from_starknet_entry
# ---------------------------------------------------------------------------


class TestFromStarknetEntry:
    def test_supported_pair_converts(self):
        entry = make_starknet_entry("BTC/USD", 6819900000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is not None
        assert result.pair == "1:0"
        assert result.price == 6819900000000

    def test_decimals_resolved_from_pair_currencies(self):
        # BTC has 8 decimals, USD has 8 decimals -> min == 8
        entry = make_starknet_entry("BTC/USD", 6819900000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is not None
        assert result.decimals == 8

    def test_eth_usd_decimals(self):
        # ETH 18 decimals, USD 8 -> min == 8
        entry = make_starknet_entry("ETH/USD", 215000000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is not None
        assert result.decimals == 8

    def test_unsupported_pair_returns_none(self):
        entry = make_starknet_entry("WSTETH/USD", 2500_000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is None

    def test_unresolvable_decimals_returns_none(self):
        # In the mapping but the asset config doesn't exist -> skip rather than publish wrong
        entry = make_starknet_entry("HYPE/USD", 1_000_000)
        with patch(
            "pragma_sdk.miden.client._resolve_pair_decimals",
            return_value=None,
        ):
            result = MidenEntry.from_starknet_entry(entry)
        assert result is None

    def test_timestamp_is_copied_from_entry(self):
        ts = 1700000000
        entry = make_starknet_entry("ETH/USD", 215000000000)
        entry.base.timestamp = ts
        result = MidenEntry.from_starknet_entry(entry)
        assert result is not None
        assert result.timestamp == ts


# ---------------------------------------------------------------------------
# STARKNET_PAIR_TO_MIDEN_FAUCET mapping
# ---------------------------------------------------------------------------


class TestMapping:
    def test_all_expected_pairs_present(self):
        expected = {"BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD", "HYPE/USD", "POL/USD"}
        assert expected == set(STARKNET_PAIR_TO_MIDEN_FAUCET.keys())

    def test_faucet_ids_are_unique(self):
        values = list(STARKNET_PAIR_TO_MIDEN_FAUCET.values())
        assert len(values) == len(set(values))

    def test_faucet_id_format(self):
        for pair, faucet_id in STARKNET_PAIR_TO_MIDEN_FAUCET.items():
            parts = faucet_id.split(":")
            assert len(parts) == 2, f"Invalid faucet_id format for {pair}: {faucet_id}"
            assert all(p.isdigit() for p in parts), f"Non-numeric faucet_id for {pair}: {faucet_id}"


# ---------------------------------------------------------------------------
# PragmaMidenClient.publish_entries
# ---------------------------------------------------------------------------


class TestPublishEntries:
    @pytest.fixture
    def mock_pm(self):
        with patch("pragma_sdk.miden.client.pm_publisher") as mock:
            mock.publish.return_value = None
            mock.init.return_value = None
            yield mock

    @pytest.fixture
    def client(self, mock_pm, tmp_path):
        config_path = write_config(tmp_path)
        c = PragmaMidenClient(
            network="testnet",
            storage_path=str(tmp_path),
            keystore_path=str(tmp_path / "keystore"),
            config_path=config_path,
        )
        c.is_initialized = True  # skip network init for these tests
        return c

    @pytest.mark.asyncio
    async def test_publish_all_success(self, client, mock_pm):
        entries = [
            MidenEntry(pair="1:0", price=6819900000000, decimals=8),
            MidenEntry(pair="2:0", price=215000000000, decimals=8),
        ]
        results = await client.publish_entries(entries)
        assert results == [True, True]
        assert mock_pm.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_empty_returns_empty(self, client, mock_pm):
        results = await client.publish_entries([])
        assert results == []
        mock_pm.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_partial_failure(self, client, mock_pm):
        mock_pm.publish.side_effect = [None, Exception("network error"), None]
        entries = [
            MidenEntry(pair="1:0", price=6819900000000, decimals=8),
            MidenEntry(pair="2:0", price=215000000000, decimals=8),
            MidenEntry(pair="3:0", price=8500000000, decimals=8),
        ]
        results = await client.publish_entries(entries)
        assert results == [True, False, True]

    @pytest.mark.asyncio
    async def test_publish_one_failure_does_not_abort(self, client, mock_pm):
        """A failure on entry N must not prevent entry N+1 from being published."""
        mock_pm.publish.side_effect = [Exception("fail"), None]
        entries = [
            MidenEntry(pair="1:0", price=6819900000000, decimals=8),
            MidenEntry(pair="2:0", price=215000000000, decimals=8),
        ]
        results = await client.publish_entries(entries)
        assert mock_pm.publish.call_count == 2
        assert results == [False, True]

    @pytest.mark.asyncio
    async def test_publish_timeout_returns_false(self, client, mock_pm, monkeypatch):
        """A pm_publisher.publish that hangs must not freeze the loop forever."""
        monkeypatch.setattr("pragma_sdk.miden.client.PUBLISH_TIMEOUT_S", 0.1)

        def slow_publish(*args, **kwargs):
            time.sleep(1)

        mock_pm.publish.side_effect = slow_publish
        entries = [MidenEntry(pair="1:0", price=6819900000000, decimals=8)]
        results = await client.publish_entries(entries)
        assert results == [False]


# ---------------------------------------------------------------------------
# PragmaMidenClient — config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    @pytest.fixture
    def mock_pm(self):
        with patch("pragma_sdk.miden.client.pm_publisher") as mock:
            yield mock

    def test_load_oracle_id_from_explicit_config_path(self, mock_pm, tmp_path):
        config_path = write_config(tmp_path)
        client = PragmaMidenClient(network="testnet", config_path=config_path)
        client._load_oracle_id()
        assert client.oracle_id == "0xafebd403be621e005bf03b9fec7fe8"

    def test_load_oracle_id_missing_file_raises(self, mock_pm, tmp_path):
        client = PragmaMidenClient(
            network="testnet",
            config_path=tmp_path / "does_not_exist.json",
        )
        with pytest.raises(RuntimeError, match="oracle_id not provided"):
            client._load_oracle_id()

    def test_load_oracle_id_missing_network_raises(self, mock_pm, tmp_path):
        config_path = tmp_path / "pragma_miden.json"
        config_path.write_text(json.dumps({"networks": {"local": {"oracle_account_id": "0xabc"}}}))
        client = PragmaMidenClient(network="testnet", config_path=config_path)
        with pytest.raises(RuntimeError, match="oracle_account_id not found"):
            client._load_oracle_id()

    def test_load_publisher_id_from_explicit_config_path(self, mock_pm, tmp_path):
        config_path = write_config(tmp_path)
        client = PragmaMidenClient(network="testnet", config_path=config_path)
        client._load_publisher_id()
        assert client.publisher_id == "0x474d7a81bb950b001661523cdd7c0b"

    def test_config_path_defaults_to_storage_path(self, mock_pm, tmp_path):
        write_config(tmp_path)
        client = PragmaMidenClient(network="testnet", storage_path=str(tmp_path))
        assert client.config_path == tmp_path / "pragma_miden.json"
        client._load_oracle_id()
        assert client.oracle_id == "0xafebd403be621e005bf03b9fec7fe8"


# ---------------------------------------------------------------------------
# PragmaMidenClient.initialize idempotence
# ---------------------------------------------------------------------------


class TestInitializeIdempotence:
    @pytest.fixture
    def mock_pm(self):
        with patch("pragma_sdk.miden.client.pm_publisher") as mock:
            mock.init.return_value = None
            yield mock

    @pytest.mark.asyncio
    async def test_existing_config_skips_pm_publisher_init(self, mock_pm, tmp_path):
        """If pragma_miden.json already exists, pm_publisher.init must NOT be called."""
        config_path = write_config(tmp_path)
        client = PragmaMidenClient(
            network="testnet",
            storage_path=str(tmp_path),
            config_path=config_path,
        )
        await client.initialize()
        mock_pm.init.assert_not_called()
        assert client.is_initialized is True
        assert client.publisher_id == "0x474d7a81bb950b001661523cdd7c0b"

    @pytest.mark.asyncio
    async def test_double_initialize_is_noop(self, mock_pm, tmp_path):
        config_path = write_config(tmp_path)
        client = PragmaMidenClient(
            network="testnet",
            storage_path=str(tmp_path),
            config_path=config_path,
        )
        await client.initialize()
        await client.initialize()
        mock_pm.init.assert_not_called()


# ---------------------------------------------------------------------------
# PragmaMidenClient — missing pm_publisher
# ---------------------------------------------------------------------------


class TestMissingPmPublisher:
    def test_raises_import_error_with_helpful_message(self):
        with patch("pragma_sdk.miden.client.pm_publisher", None):
            with pytest.raises(ImportError, match=r"pip install pragma-sdk\[miden\]"):
                PragmaMidenClient(network="testnet")
