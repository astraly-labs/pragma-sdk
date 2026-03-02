import logging
from typing import List, Optional, Union, Dict, Any

from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.client import Client
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner
from starknet_py.net.models import StarknetChainId

from pragma_sdk.common.exceptions import ClientException
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import Address
from pragma_sdk.common.types.client import PragmaClient

from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.onchain.constants import CHAIN_IDS, CONTRACT_ADDRESSES
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.types import (
    PrivateKey,
    Contract,
    NetworkName,
    ContractAddresses,
    Network,
    PublishEntriesOnChainResult,
)
from pragma_sdk.onchain.mixins import (
    OracleMixin,
    PublisherRegistryMixin,
    RandomnessMixin,
    MerkleFeedMixin,
    MidenMixin,
    MidenEntry
)
from pragma_sdk.onchain.utils import get_full_node_client_from_network

from pragma_sdk.offchain.types import PublishEntriesAPIResult
from pathlib import Path
import pm_publisher


logger = get_pragma_sdk_logger()
logger.setLevel(logging.INFO)


class PragmaOnChainClient(  # type: ignore[misc]
    PragmaClient,
    OracleMixin,
    PublisherRegistryMixin,
    RandomnessMixin,
    MerkleFeedMixin,
):
    """
    Client for interacting with Pragma on Starknet.

    :param network: Target network for the client. Can be a URL string, or one of
                    ``"mainnet"``, ``"sepolia"`` or ``"devnet"``
    :param account_private_key: Optional private key for requests. Not necessary if not making
                                network updates.
                                Can be either an hexadecimal string 0x prefixed, an integer or
                                a KeyStore type.
                                The KeyStore is a tuple of two string [str, str], which are
                                ["path/to/the/keystore", "password_to_unlock_the_keystore"].
    :param account_contract_address: Optional account contract address.  Not necessary if not
                                     making network updates.
                                     Can either be an integer or an hexadecimal string 0x prefixed.
    :param contract_addresses_config: Optional Contract Addresses for Pragma contracts.
                                      Will default to the provided network but must be set if using
                                      non standard contracts.
    :param port: Optional port to interact with local node. Will default to 5050.
    :param chain_name: A str-representation of the chain if a URL string is given for `network`.
                       Must be one of ``"mainnet"``, ``"sepolia"`` or ``"devnet"``.
    """

    is_user_client: bool = False
    account_contract_address: Optional[Address] = None
    account: Account = None
    full_node_client: FullNodeClient = None
    client: Client = None
    execution_config: ExecutionConfig

    def __init__(
        self,
        network: Network = "sepolia",
        account_private_key: Optional[PrivateKey] = None,
        account_contract_address: Optional[int | str] = None,
        contract_addresses_config: Optional[ContractAddresses] = None,
        port: Optional[int] = None,
        chain_name: Optional[NetworkName] = None,
        execution_config: Optional[ExecutionConfig] = None,
    ):
        full_node_client: FullNodeClient = get_full_node_client_from_network(
            network, port=port
        )
        self.full_node_client = full_node_client
        self.client = full_node_client

        if network.startswith("http") and chain_name is None:  # type: ignore[union-attr]
            raise ClientException(
                f"Network provided is a URL: {network} but `chain_name` is not provided."
            )

        self.network = (
            network if not (network.startswith("http") and chain_name) else chain_name  # type: ignore[union-attr]
        )

        if execution_config is not None:
            self.execution_config = execution_config
        else:
            self.execution_config = ExecutionConfig(auto_estimate=True)

        if account_contract_address and account_private_key:
            self._setup_account_client(
                CHAIN_IDS[self.network],
                account_private_key,
                account_contract_address,
            )

        if not contract_addresses_config:
            contract_addresses_config = CONTRACT_ADDRESSES[self.network]  # type: ignore[index]

        self.contract_addresses_config = contract_addresses_config
        self._setup_contracts()

    def _setup_contracts(self):
        """
        Setup the contracts for the client.
        For now, this includes the Oracle and PublisherRegistry contracts.
        """

        provider = self.account if self.account else self.client
        self.oracle = Contract(
            address=self.contract_addresses_config.oracle_proxy_addresss,
            abi=ABIS["pragma_Oracle"],
            provider=provider,
            cairo_version=1,
        )
        self.publisher_registry = Contract(
            address=self.contract_addresses_config.publisher_registry_address,
            abi=ABIS["pragma_PublisherRegistry"],
            provider=provider,
            cairo_version=1,
        )
        self.summary_stats = Contract(
            address=self.contract_addresses_config.summary_stats_address,
            abi=ABIS["pragma_SummaryStats"],
            provider=provider,
            cairo_version=1,
        )

    def _process_secret_key(self, private_key: PrivateKey) -> KeyPair:
        """Converts a Private Key to a KeyPair."""
        if isinstance(private_key, int):
            return KeyPair.from_private_key(private_key)
        elif isinstance(private_key, tuple):
            path, password = private_key
            return KeyPair.from_keystore(path, password)
        elif isinstance(private_key, str):
            return KeyPair.from_private_key(int(private_key, 16))

    def _setup_account_client(
        self,
        chain_id: StarknetChainId,
        private_key: PrivateKey,
        account_contract_address: int | str,
    ):
        self.signer = StarkCurveSigner(
            account_contract_address,
            self._process_secret_key(private_key),
            chain_id,
        )
        self.account = Account(
            address=account_contract_address,
            client=self.client,
            signer=self.signer,
        )
        self.client = self.account.client
        self.is_user_client = True
        if isinstance(account_contract_address, str):
            account_contract_address = int(account_contract_address, 16)
        self.account_contract_address = account_contract_address

    @property
    def account_address(self) -> Address:
        """
        Return the account address.
        """

        return self.account.address  # type: ignore[no-any-return]

    async def get_balance(self, account_contract_address, token_address=None) -> int:
        """
        Get the balance of an account given the account contract address and token address.

        :param account_contract_address: The account contract address.
        :param token_address: The token address. If None, will use ETH as the token address.
        :return: The balance of the account.
        """

        client = Account(
            address=account_contract_address,
            client=self.client,
            key_pair=KeyPair.from_private_key(1),
            chain=CHAIN_IDS[self.network],
        )
        return await client.get_balance(token_address)  # type: ignore[no-any-return]

    async def get_block_number(self) -> int:
        """Returns the current block number."""
        return await self.full_node_client.get_block_number()  # type: ignore[no-any-return]

    async def publish_entries(
        self, entries: List[Entry]
    ) -> PublishEntriesOnChainResult:
        """
        Publish entries on-chain.

        :param entries: List of Entry objects
        :return: List of InvokeResult objects
        """
        return await self.publish_many(entries)
    
    def _create_full_node_client(self, rpc_url: str) -> FullNodeClient:
        """Create a new full node client with the given RPC URL."""
        return FullNodeClient(node_url=rpc_url)


class PragmaMidenOnChainClient(PragmaClient, MidenMixin):
    """
    
    This is a simplified client that only provides Miden oracle functionality.

    :param network: Target network for the client. Can be a URL string, or one of
                    ``"testnet"``, or ``"devnet"``
    :param oracle_id: Optional oracle ID for the Miden oracle
    :param storage_path: Optional path where the Miden storage will be kept
    """
    PRAGMA_MIDEN_CONFIG = "pragma_miden.json"
    PUBLISHER_ID_KEY = "publisher_account_id"

    def __init__(
        self,
        network: Network = "testnet",
        oracle_id: Optional[str] = None,
        storage_path: Optional[str] = None,
        keystore_path= None

    ):
        self.network = network
        self.oracle_id = oracle_id
        self.storage_path = storage_path
        self.keystore_path = keystore_path
        self.is_initialized = False
        self.publisher_id = None

    async def initialize(self) -> None:
        """
        Initialize the Miden client.
        """
        if not self.is_initialized:
            await self.init_miden(self.oracle_id, self.storage_path, self.keystore_path)
    
    async def init_miden(self, oracle_id=None, storage_path=None, keystore_path=None):
        """
        Initialize the Miden publisher.
        """
        try:
            if storage_path:
                # Ensure miden_storage directory exists in the specified path
                miden_dir = Path(storage_path) / "miden_storage"
                miden_dir.mkdir(parents=True, exist_ok=True)
            else:
                # Create miden_storage in current directory
                Path("miden_storage").mkdir(exist_ok=True)
            
            print(f"Initializing with oracle_id={oracle_id}, storage_path={storage_path}, network={self.network}")
            result = pm_publisher.init(oracle_id, storage_path, keystore_path, self.network)
            self.is_initialized = True
            self.storage_path = storage_path
            self.keystore_path = keystore_path
            
            # Load publisher ID after initialization
            await self._load_publisher_id()
            
            print(f"Miden publisher initialized: {result}")
            
        except Exception as e:
            print(f"Failed to initialize Miden publisher: {e}")
            raise

    async def _load_publisher_id(self):
        """Load publisher ID from pragma_miden.json config file."""
        try:
            # pragma_miden.json is always created in the current directory
            config_path = Path(self.PRAGMA_MIDEN_CONFIG)
            if not config_path.exists():
                raise RuntimeError(f"Config file not found: {config_path}")
                
            with open(config_path) as f:
                config = json.load(f)
                
            # Check for the new format with networks
            if 'networks' in config and self.network in config['networks']:
                network_config = config['networks'][self.network]
                if self.PUBLISHER_ID_KEY in network_config:
                    self.publisher_id = network_config[self.PUBLISHER_ID_KEY]
                    print(f"Loaded publisher ID: {self.publisher_id} for network: {self.network}")
                    return True
                
            raise RuntimeError(f"Publisher ID not found in config file for network: {self.network}")
            
        except Exception as e:
            print(f"Failed to load publisher ID: {e}")
            raise

    async def publish_entries(self, entries):
        """
        Publish entries to the Miden oracle.
        """
        if not self.is_initialized:
            # Try to load publisher ID from config file first
            try:
                await self._load_publisher_id()
                # If we successfully loaded the publisher ID, mark as initialized
                self.is_initialized = True
                print("Found existing publisher configuration, skipping initialization")
            except Exception as e:
                # If loading fails, do full initialization
                print(f"No existing publisher found: {e}, performing full initialization")
                await self.initialize()
        
        return await self.publish_many(entries)
    
    async def publish_many(self, entries):
        """
        Publish multiple price entries to the Miden oracle.
        """
        if not entries:
            print("publish_many received no entries to publish. Skipping")
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
            results.extend(result)
            print(f"Published batch of {len(batch)} entries")
            
        return results

    async def _publish_batch(self, entries):
        """
        Publish a batch of entries one by one.
        """
        try:
            results = []
            for entry in entries:
                result = pm_publisher.publish(
                    pair=entry.pair,
                    price=entry.price,
                    decimals=entry.decimals,
                    timestamp=entry.timestamp,
                    storage_path=self.storage_path,
                    keystore_path = self.keystore_path,
                    network=self.network
                )
                results.append(result)
                
            return results
            
        except Exception as e:
            print(f"Failed to publish batch: {e}")
            raise

    async def get_entry(self, pair):
        """
        Get the latest entry for a pair from this publisher.
        """
        if not self.is_initialized:
            raise RuntimeError("Miden publisher not initialized. Call init_miden() first.")
            
        if self.publisher_id is None:
            raise RuntimeError("Publisher ID not loaded")
            
        try:
            result = pm_publisher.get_entry(
                pair=pair,
                storage_path=self.storage_path,
                network=self.network
            )
            print(f"Successfully retrieved entry for {pair}")
            return {"status": "success", "data": result}
            
        except Exception as e:
            print(f"Failed to get entry: {e}")
            raise

