import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import time

import pm_publisher
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.types import UnixTimestamp, Address

logger = get_pragma_sdk_logger()

class MidenEntry:
    """Represents a price entry for the Miden oracle."""
    def __init__(
        self,
        pair: str,
        price: int,
        decimals: int,
        timestamp: Optional[UnixTimestamp] = None
    ):
        self.pair = pair
        self.price = price
        self.decimals = decimals
        self.timestamp = timestamp or int(time.time())
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "price": self.price,
            "decimals": self.decimals,
            "timestamp": self.timestamp
        }

class MidenMixin:
    """
    Mixin class for interacting with the Pragma Miden oracle implementation.
    Provides an interface to publish price data to the Miden oracle network.
    """
    
    PRAGMA_MIDEN_CONFIG = "pragma_miden.json"
    PUBLISHER_ID_KEY = "publisher_account_id"
    
    publisher_id: Optional[str]
    storage_path: Optional[str]
    network: str
    is_initialized: bool = False
    
    async def init_miden(self, oracle_id: Optional[str] = None, storage_path: Optional[str] = None, network : Optional[str] = "testnet") -> None:
        """
        Initialize the Miden publisher. This will:
        1. Create a new publisher wallet if none exists
        2. Store the wallet info in the SQLite database
        3. Set up the connection to the oracle network
        
        Args:
            oracle_id: oracle contract address
            storage_path: Path where the SQLite database will be stored
        """
        try:
            if storage_path:
                # Ensure miden_storage directory exists in the specified path
                miden_dir = Path(storage_path) / "miden_storage"
                miden_dir.mkdir(parents=True, exist_ok=True)
            else:
                # Create miden_storage in current directory
                Path("miden_storage").mkdir(exist_ok=True)
            
            result = pm_publisher.init(oracle_id, storage_path, network)
            self.is_initialized = True
            self.storage_path = storage_path
            self.network = network
            
            # Load publisher ID after initialization
            await self._load_publisher_id()
            
            logger.info(f"Miden publisher initialized: {result}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Miden publisher: {e}")
            raise

    async def _load_publisher_id(self) -> None:
        """Load publisher ID from pragma_miden.json config file."""
        try:
            # pragma_miden.json is always created in the current directory
            config_path = Path(self.PRAGMA_MIDEN_CONFIG)
            if not config_path.exists():
                raise RuntimeError(f"Config file not found: {config_path}")
                
            with open(config_path) as f:
                config = json.load(f)
                
            if 'data' not in config or self.PUBLISHER_ID_KEY not in config['data']:
                raise RuntimeError("Publisher ID not found in config file")
                
            self.publisher_id = config['data'][self.PUBLISHER_ID_KEY]
            logger.debug(f"Loaded publisher ID: {self.publisher_id}")
            
        except Exception as e:
            logger.error(f"Failed to load publisher ID: {e}")
            raise

    async def publish_many(self, entries: List[MidenEntry]) -> List[Dict[str, Any]]:
        """
        Publish multiple price entries to the Miden oracle.
        
        Args:
            entries: List of MidenEntry objects to publish
            
        Returns:
            List of publication results
        """
        if not entries:
            logger.warning("publish_many received no entries to publish. Skipping")
            return []

        if not self.is_initialized:
            raise RuntimeError("Miden publisher not initialized. Call init_miden() first.")
        
        if self.publisher_id is None:
            raise RuntimeError("Publisher ID not loaded")

        results = []
        # Process entries in smaller batches since we're making individual calls
        batch_size = 5
        
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            result = await self._publish_batch(batch)
            results.append(result)
            logger.debug(f"Published batch of {len(batch)} entries")
            
        return results

    async def _publish_batch(self, entries: List[MidenEntry]) -> Dict[str, Any]:
        """
        Publish a batch of entries one by one.
        
        Args:
            entries: List of entries to publish in this batch
            
        Returns:
            Publication result for the batch
        """
        try:
            results = []
            for entry in entries:
                result = pm_publisher.publish(
                    publisher=self.publisher_id,
                    pair=entry.pair,
                    price=entry.price,
                    decimals=entry.decimals,
                    timestamp=entry.timestamp,
                    storage_path=self.storage_path,
                    network = self.network
                )
                results.append(result)
                
            return {
                "status": "success", 
                "message": f"Successfully published {len(entries)} entries",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Failed to publish batch: {e}")
            raise

    async def publish(
        self,
        pair: str,
        price: int,
        decimals: int,
        timestamp: Optional[UnixTimestamp] = None,
    ) -> Dict[str, Any]:
        """
        Publish a single price entry to the Miden oracle.
        
        Args:
            pair: Trading pair (e.g. "BTC/USD")
            price: Price value
            decimals: Number of decimals in price value
            timestamp: Optional Unix timestamp, uses current time if not provided
            
        Returns:
            Publication result from publisher
        """
        entry = MidenEntry(pair, price, decimals, timestamp)
        results = await self.publish_many([entry])
        return results[0] if results else {"status": "error", "message": "Failed to publish"}

    async def get_entry(self, pair: str) -> Dict[str, Any]:
        """
        Get the latest entry for a pair from this publisher.
        
        Args:
            pair: Trading pair (e.g. "BTC/USD")
            
        Returns:
            Latest entry data
        """
        if not self.is_initialized:
            raise RuntimeError("Miden publisher not initialized. Call init_miden() first.")
            
        if self.publisher_id is None:
            raise RuntimeError("Publisher ID not loaded")
            
        try:
            result = pm_publisher.get_entry(
                publisher_id=self.publisher_id,
                pair=pair,
                storage_path=self.storage_path,
                network = self.network
            )
            logger.debug(f"Successfully retrieved entry for {pair}")
            return {"status": "success", "data": result}
            
        except Exception as e:
            logger.error(f"Failed to get entry: {e}")
            raise

    async def sync(self) -> Dict[str, Any]:
        """
        Sync the publisher state with the network.
        
        Returns:
            Sync status and result
        """
        if not self.is_initialized:
            raise RuntimeError("Miden publisher not initialized. Call init_miden() first.")
        
        try:
            result = pm_publisher.sync(storage_path=self.storage_path, network = self.network)
            logger.debug("Successfully synced publisher state")
            return {"status": "success", "message": result}
            
        except Exception as e:
            logger.error(f"Failed to sync state: {e}")
            raise
