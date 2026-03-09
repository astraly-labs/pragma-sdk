import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

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


def make_config(tmp_path: Path, network: str = "testnet") -> Path:
    """Write a minimal pragma_miden.json in tmp_path and return the path."""
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
    return tmp_path


# ---------------------------------------------------------------------------
# MidenEntry.from_starknet_entry
# ---------------------------------------------------------------------------


class TestFromStarknetEntry:
    def test_supported_pair_converts(self):
        entry = make_starknet_entry("BTC/USD", 68199_000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is not None
        assert result.pair == "1:0"
        assert result.price == 68199_000000
        assert result.decimals == 6

    def test_unsupported_pair_returns_none(self):
        entry = make_starknet_entry("WSTETH/USD", 2500_000000)
        result = MidenEntry.from_starknet_entry(entry)
        assert result is None

    def test_all_supported_pairs_convert(self):
        for starknet_pair, faucet_id in STARKNET_PAIR_TO_MIDEN_FAUCET.items():
            entry = make_starknet_entry(starknet_pair, 1_000000)
            result = MidenEntry.from_starknet_entry(entry)
            assert result is not None, f"{starknet_pair} should be supported"
            assert result.pair == faucet_id

    def test_timestamp_is_copied_from_entry(self):
        ts = 1700000000
        entry = make_starknet_entry("ETH/USD", 2000_000000)
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
        assert len(values) == len(set(values)), "Duplicate faucet_id detected"

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
        """Patch pm_publisher at the module level."""
        with patch("pragma_sdk.miden.client.pm_publisher") as mock:
            mock.publish.return_value = None
            mock.init.return_value = None
            yield mock

    @pytest.fixture
    def client(self, mock_pm, tmp_path):
        config_dir = make_config(tmp_path)
        with patch.object(Path, "cwd", return_value=config_dir):
            c = PragmaMidenClient(network="testnet")
            c.is_initialized = True  # skip init
            c.storage_path = str(config_dir)
            c.keystore_path = str(config_dir / "keystore")
            return c

    @pytest.mark.asyncio
    async def test_publish_all_success(self, client, mock_pm):
        entries = [
            MidenEntry(pair="1:0", price=68199_000000, decimals=6),
            MidenEntry(pair="2:0", price=2150_000000, decimals=6),
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
            MidenEntry(pair="1:0", price=68199_000000, decimals=6),
            MidenEntry(pair="2:0", price=2150_000000, decimals=6),
            MidenEntry(pair="3:0", price=85_000000, decimals=6),
        ]
        results = await client.publish_entries(entries)
        assert results == [True, False, True]

    @pytest.mark.asyncio
    async def test_publish_one_failure_does_not_abort(self, client, mock_pm):
        """A failure on entry N must not prevent entry N+1 from being published."""
        mock_pm.publish.side_effect = [Exception("fail"), None]
        entries = [
            MidenEntry(pair="1:0", price=68199_000000, decimals=6),
            MidenEntry(pair="2:0", price=2150_000000, decimals=6),
        ]
        results = await client.publish_entries(entries)
        assert mock_pm.publish.call_count == 2
        assert results[1] is True


# ---------------------------------------------------------------------------
# PragmaMidenClient._load_oracle_id / _load_publisher_id
# ---------------------------------------------------------------------------


class TestConfigLoading:
    @pytest.fixture
    def mock_pm(self):
        with patch("pragma_sdk.miden.client.pm_publisher") as mock:
            yield mock

    def test_load_oracle_id_from_json(self, mock_pm, tmp_path):
        make_config(tmp_path)
        client = PragmaMidenClient(network="testnet")
        with patch("pragma_sdk.miden.client.Path") as MockPath:
            MockPath.return_value.exists.return_value = True
            MockPath.return_value.__truediv__ = lambda s, o: tmp_path / o
            config_path = tmp_path / "pragma_miden.json"
            MockPath.return_value = config_path
            # Direct test via actual file
            import os
            orig = os.getcwd()
            os.chdir(tmp_path)
            try:
                client._load_oracle_id()
                assert client.oracle_id == "0xafebd403be621e005bf03b9fec7fe8"
            finally:
                os.chdir(orig)

    def test_load_oracle_id_missing_file_raises(self, mock_pm, tmp_path):
        client = PragmaMidenClient(network="testnet")
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)  # empty dir, no pragma_miden.json
        try:
            with pytest.raises(RuntimeError, match="oracle_id not provided"):
                client._load_oracle_id()
        finally:
            os.chdir(orig)

    def test_load_oracle_id_missing_network_raises(self, mock_pm, tmp_path):
        config = {"networks": {"local": {"oracle_account_id": "0xabc"}}}
        (tmp_path / "pragma_miden.json").write_text(json.dumps(config))
        client = PragmaMidenClient(network="testnet")
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            with pytest.raises(RuntimeError, match="oracle_account_id not found"):
                client._load_oracle_id()
        finally:
            os.chdir(orig)

    def test_load_publisher_id_from_json(self, mock_pm, tmp_path):
        make_config(tmp_path)
        client = PragmaMidenClient(network="testnet")
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            client._load_publisher_id()
            assert client.publisher_id == "0x474d7a81bb950b001661523cdd7c0b"
        finally:
            os.chdir(orig)


# ---------------------------------------------------------------------------
# PragmaMidenClient — missing pm_publisher
# ---------------------------------------------------------------------------


class TestMissingPmPublisher:
    def test_raises_import_error_with_helpful_message(self):
        with patch("pragma_sdk.miden.client.pm_publisher", None):
            with pytest.raises(ImportError, match="pip install pragma-sdk\\[miden\\]"):
                PragmaMidenClient(network="testnet")
