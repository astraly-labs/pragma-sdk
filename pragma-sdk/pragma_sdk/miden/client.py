import json
import time
from pathlib import Path
from typing import Optional, List

from pragma_sdk.common.logging import get_pragma_sdk_logger

try:
    import pm_publisher
except ImportError:
    pm_publisher = None  # type: ignore[assignment]

logger = get_pragma_sdk_logger()


class MidenEntry:
    """Represents a price entry for the Miden oracle."""

    def __init__(
        self,
        pair: str,
        price: int,
        decimals: int,
        timestamp: Optional[int] = None,
    ):
        self.pair = pair
        self.price = price
        self.decimals = decimals
        self.timestamp = timestamp or int(time.time())

    @classmethod
    def from_starknet_entry(cls, entry: object) -> Optional["MidenEntry"]:
        """
        Convert a Starknet Entry to a MidenEntry.
        Returns None if the pair is not supported on Miden.
        """
        pair_id = entry.get_pair_id()  # type: ignore[attr-defined]
        faucet_id = STARKNET_PAIR_TO_MIDEN_FAUCET.get(pair_id)
        if faucet_id is None:
            return None
        return cls(
            pair=faucet_id,
            price=entry.price,  # type: ignore[attr-defined]
            decimals=6,
            timestamp=entry.base.timestamp,  # type: ignore[attr-defined]
        )

# Mapping from Starknet pair_id (e.g. "BTC/USD") to Miden faucet_id (e.g. "1:0")
STARKNET_PAIR_TO_MIDEN_FAUCET: dict[str, str] = {
    "BTC/USD": "1:0",
    "ETH/USD": "2:0",
    "SOL/USD": "3:0",
    "BNB/USD": "4:0",
    "XRP/USD": "5:0",
    "HYPE/USD": "6:0",
    "POL/USD": "7:0",
}

class PragmaMidenClient:
    """
    Standalone client for publishing price data to the Pragma Miden oracle.

    Completely independent from PragmaOnChainClient (Starknet) — a failure
    here has zero impact on Starknet publishing.

    :param network: "testnet", "devnet", or "local"
    :param oracle_id: Oracle account ID (can be omitted if already initialized)
    :param storage_path: Directory where the Miden SQLite store is kept
    :param keystore_path: Directory where the Miden keystore is kept
    """

    PRAGMA_MIDEN_CONFIG = "pragma_miden.json"

    def __init__(
        self,
        network: str = "testnet",
        oracle_id: Optional[str] = None,
        storage_path: Optional[str] = None,
        keystore_path: Optional[str] = None,
    ):
        if pm_publisher is None:
            raise ImportError(
                "pm_publisher is not installed. "
                "Install it with: pip install pragma-sdk[miden]"
            )
        self.network = network
        self.oracle_id = oracle_id or ""
        self.storage_path = storage_path
        self.keystore_path = keystore_path
        self.publisher_id: Optional[str] = None
        self.is_initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Initialize the Miden publisher account (creates it if needed).
        Safe to call multiple times — no-op if already initialized.
        If oracle_id was not passed at construction, reads it from pragma_miden.json.
        """
        if self.is_initialized:
            return

        if not self.oracle_id:
            self._load_oracle_id()

        if self.storage_path:
            (Path(self.storage_path) / "miden_storage").mkdir(parents=True, exist_ok=True)
        else:
            Path("miden_storage").mkdir(exist_ok=True)

        pm_publisher.init(
            oracle_id=self.oracle_id,
            storage_path=self.storage_path,
            keystore_path=self.keystore_path,
            network=self.network,
        )
        self.is_initialized = True
        self._load_publisher_id()
        logger.info(f"Miden publisher initialized (network={self.network}, id={self.publisher_id})")

    def _load_publisher_id(self) -> None:
        config_path = Path(self.PRAGMA_MIDEN_CONFIG)
        if not config_path.exists():
            raise RuntimeError(f"Config file not found: {config_path}")
        with open(config_path) as f:
            config = json.load(f)
        ids = config.get("networks", {}).get(self.network, {}).get("publisher_account_ids")
        if not ids:
            raise RuntimeError(f"publisher_account_ids not found in config for network: {self.network}")
        self.publisher_id = ids[0]

    def _load_oracle_id(self) -> None:
        config_path = Path(self.PRAGMA_MIDEN_CONFIG)
        if not config_path.exists():
            raise RuntimeError(
                f"oracle_id not provided and config file not found: {config_path}"
            )
        with open(config_path) as f:
            config = json.load(f)
        oracle_id = config.get("networks", {}).get(self.network, {}).get("oracle_account_id")
        if not oracle_id:
            raise RuntimeError(
                f"oracle_account_id not found in config for network: {self.network}"
            )
        self.oracle_id = oracle_id

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_entries(self, entries: List[MidenEntry]) -> List[bool]:
        """
        Publish price entries to the Miden oracle.
        Lazily initializes if needed (loads existing config, or runs full init).
        Returns a list of booleans indicating success per entry.
        """
        if not entries:
            logger.warning("publish_entries: no entries to publish")
            return []

        if not self.is_initialized:
            try:
                self._load_publisher_id()
                self.is_initialized = True
                logger.info("Reusing existing Miden publisher config")
            except Exception:
                logger.info("No existing Miden config found — running full init")
                await self.initialize()

        results = []
        for entry in entries:
            try:
                pm_publisher.publish(
                    entry.pair,
                    entry.price,
                    entry.decimals,
                    entry.timestamp,
                    storage_path=self.storage_path,
                    keystore_path=self.keystore_path,
                    network=self.network,
                )
                results.append(True)
            except Exception as e:
                logger.error(f"Failed to publish {entry.pair}: {e}")
                results.append(False)

        return results

    async def get_entry(self, pair: str) -> Optional[str]:
        """Fetch the latest published entry for a pair."""
        if not self.is_initialized:
            raise RuntimeError("Call initialize() or publish_entries() first.")
        try:
            return pm_publisher.get_entry(
                pair,
                storage_path=self.storage_path,
                keystore_path=self.keystore_path,
                network=self.network,
            )
        except Exception as e:
            logger.error(f"Failed to get entry for {pair}: {e}")
            raise

    async def sync(self) -> None:
        """Sync the local store with the network."""
        if not self.is_initialized:
            raise RuntimeError("Call initialize() or publish_entries() first.")
        pm_publisher.sync(
            storage_path=self.storage_path,
            keystore_path=self.keystore_path,
            network=self.network,
        )
