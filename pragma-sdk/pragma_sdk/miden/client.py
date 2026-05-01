import asyncio
import json
import time
from pathlib import Path
from typing import Optional, List, Union

from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.exceptions import UnsupportedAssetError
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.pair import Pair

try:
    import pm_publisher
except ImportError:
    pm_publisher = None  # type: ignore[assignment]

logger = get_pragma_sdk_logger()

# Bound every blocking pm_publisher call so a stuck Miden node cannot
# starve the event loop indefinitely.
INIT_TIMEOUT_S = 60
PUBLISH_BATCH_TIMEOUT_S = 60
GET_ENTRY_TIMEOUT_S = 15
SYNC_TIMEOUT_S = 30

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
        Returns None if the pair is not supported on Miden, or if the pair's
        decimals cannot be resolved (skipping is safer than publishing a
        wrong-scaled price).
        """
        pair_id = entry.get_pair_id()  # type: ignore[attr-defined]
        faucet_id = STARKNET_PAIR_TO_MIDEN_FAUCET.get(pair_id)
        if faucet_id is None:
            return None

        decimals = _resolve_pair_decimals(pair_id)
        if decimals is None:
            return None

        return cls(
            pair=faucet_id,
            price=entry.price,  # type: ignore[attr-defined]
            decimals=decimals,
            timestamp=entry.base.timestamp,  # type: ignore[attr-defined]
        )


def _resolve_pair_decimals(pair_id: str) -> Optional[int]:
    """Look up the SDK's native decimals for a pair."""
    try:
        base, quote = pair_id.split("/", 1)
    except ValueError:
        logger.warning(f"Unexpected pair_id format: {pair_id!r}")
        return None
    try:
        pair = Pair.from_asset_configs(
            AssetConfig.from_ticker(base),
            AssetConfig.from_ticker(quote),
        )
        return pair.decimals()
    except (UnsupportedAssetError, ValueError) as e:
        logger.warning(f"Cannot resolve decimals for {pair_id}: {e}")
        return None


class PragmaMidenClient:
    """
    Standalone client for publishing price data to the Pragma Miden oracle.

    Completely independent from PragmaOnChainClient (Starknet) — a failure
    here has zero impact on Starknet publishing. Every blocking call into
    the underlying pm_publisher Rust binding is offloaded via
    ``asyncio.to_thread`` and bounded by ``asyncio.wait_for``, so the
    event loop is never stuck on Miden.

    :param network: "testnet", "devnet", or "local"
    :param oracle_id: Oracle account ID (can be omitted if already initialized)
    :param storage_path: Directory where the Miden SQLite store is kept
    :param keystore_path: Directory where the Miden keystore is kept
    :param config_path: Path to ``pragma_miden.json``. Defaults to
        ``<storage_path>/pragma_miden.json`` if storage_path is set, else
        ``./pragma_miden.json`` relative to the current working directory.
    """

    PRAGMA_MIDEN_CONFIG = "pragma_miden.json"

    def __init__(
        self,
        network: str = "testnet",
        oracle_id: Optional[str] = None,
        storage_path: Optional[str] = None,
        keystore_path: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None,
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
        self.config_path = self._resolve_config_path(config_path, storage_path)
        self.publisher_id: Optional[str] = None
        self.is_initialized = False

    @classmethod
    def _resolve_config_path(
        cls,
        config_path: Optional[Union[str, Path]],
        storage_path: Optional[str],
    ) -> Path:
        if config_path is not None:
            return Path(config_path)
        if storage_path is not None:
            return Path(storage_path) / cls.PRAGMA_MIDEN_CONFIG
        return Path(cls.PRAGMA_MIDEN_CONFIG)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Initialize the Miden publisher account.

        If a config already exists for this network, reuses it (idempotent).
        Otherwise runs ``pm_publisher.init`` which creates a new on-chain
        publisher account. The init call is offloaded to a thread and bounded
        by ``INIT_TIMEOUT_S`` so a stuck Miden node cannot freeze the loop.
        """
        if self.is_initialized:
            return

        # Reuse existing config if present — pm_publisher.init is NOT idempotent
        # on the Rust side (it always creates a new publisher account).
        try:
            self._load_publisher_id()
            if not self.oracle_id:
                self._load_oracle_id()
            self.is_initialized = True
            logger.info(
                f"Miden publisher reused from config (network={self.network}, "
                f"id={self.publisher_id})"
            )
            return
        except RuntimeError:
            pass

        if not self.oracle_id:
            self._load_oracle_id()

        if self.storage_path:
            (Path(self.storage_path) / "miden_storage").mkdir(
                parents=True, exist_ok=True
            )
        else:
            Path("miden_storage").mkdir(exist_ok=True)

        await asyncio.wait_for(
            asyncio.to_thread(
                pm_publisher.init,
                oracle_id=self.oracle_id,
                storage_path=self.storage_path,
                keystore_path=self.keystore_path,
                network=self.network,
            ),
            timeout=INIT_TIMEOUT_S,
        )
        self._load_publisher_id()
        self.is_initialized = True
        logger.info(
            f"Miden publisher initialized (network={self.network}, id={self.publisher_id})"
        )

    def _load_publisher_id(self) -> None:
        if not self.config_path.exists():
            raise RuntimeError(f"Config file not found: {self.config_path}")
        with open(self.config_path) as f:
            config = json.load(f)
        ids = (
            config.get("networks", {})
            .get(self.network, {})
            .get("publisher_account_ids")
        )
        if not ids:
            raise RuntimeError(
                f"publisher_account_ids not found in {self.config_path} "
                f"for network: {self.network}"
            )
        self.publisher_id = ids[0]

    def _load_oracle_id(self) -> None:
        if not self.config_path.exists():
            raise RuntimeError(
                f"oracle_id not provided and config file not found: {self.config_path}"
            )
        with open(self.config_path) as f:
            config = json.load(f)
        oracle_id = (
            config.get("networks", {}).get(self.network, {}).get("oracle_account_id")
        )
        if not oracle_id:
            raise RuntimeError(
                f"oracle_account_id not found in {self.config_path} "
                f"for network: {self.network}"
            )
        self.oracle_id = oracle_id

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_entries(self, entries: List[MidenEntry]) -> List[bool]:
        """
        Publish price entries to the Miden oracle in a single batched transaction.

        All entries are submitted via ``pm_publisher.publish_batch`` in **one**
        on-chain transaction. The result is therefore all-or-nothing: on
        success returns ``[True] * N``, on failure returns ``[False] * N``.
        Returning a list (rather than a single bool) keeps the call shape
        aligned with upstream callers and lets us evolve later without an
        API break.
        """
        if not entries:
            logger.warning("publish_entries: no entries to publish")
            return []

        if not self.is_initialized:
            await self.initialize()

        batch = [(e.pair, e.price, e.decimals, e.timestamp) for e in entries]
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    pm_publisher.publish_batch,
                    batch,
                    storage_path=self.storage_path,
                    keystore_path=self.keystore_path,
                    network=self.network,
                ),
                timeout=PUBLISH_BATCH_TIMEOUT_S,
            )
            return [True] * len(entries)
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout (>{PUBLISH_BATCH_TIMEOUT_S}s) publishing batch of "
                f"{len(entries)} entries to Miden"
            )
            return [False] * len(entries)
        except Exception as e:
            logger.error(f"Failed to publish batch of {len(entries)} entries: {e}")
            return [False] * len(entries)

    async def get_entry(self, pair: str) -> Optional[MidenEntry]:
        """
        Fetch the latest published entry for a pair. Returns ``None`` on
        failure (network error, timeout, malformed response).
        """
        if not self.is_initialized:
            raise RuntimeError("Call initialize() or publish_entries() first.")
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    pm_publisher.get_entry,
                    pair,
                    storage_path=self.storage_path,
                    keystore_path=self.keystore_path,
                    network=self.network,
                ),
                timeout=GET_ENTRY_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout (>{GET_ENTRY_TIMEOUT_S}s) fetching entry for {pair}")
            return None
        except Exception as e:
            logger.error(f"Failed to get entry for {pair}: {e}")
            return None

        try:
            data = json.loads(raw)
            return MidenEntry(
                pair=data["faucet_id"],
                price=int(data["price"]),
                decimals=int(data["decimals"]),
                timestamp=int(data["timestamp"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Malformed get_entry payload for {pair}: {raw!r} ({e})")
            return None

    async def sync(self) -> None:
        """Sync the local store with the network."""
        if not self.is_initialized:
            raise RuntimeError("Call initialize() or publish_entries() first.")
        await asyncio.wait_for(
            asyncio.to_thread(
                pm_publisher.sync,
                storage_path=self.storage_path,
                keystore_path=self.keystore_path,
                network=self.network,
            ),
            timeout=SYNC_TIMEOUT_S,
        )
