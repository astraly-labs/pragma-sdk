import logging
from typing import Optional

from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner

from pragma.core.abis import ABIS
from pragma.core.contract import Contract
from pragma.core.mixins import (
    NonceMixin,
    OracleMixin,
    PublisherRegistryMixin,
    RandomnessMixin,
    TransactionMixin,
)
from pragma.core.types import (
    CHAIN_IDS,
    CONTRACT_ADDRESSES,
    ClientException,
    ContractAddresses,
    get_client_from_network,
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PragmaClient(
    NonceMixin,
    OracleMixin,
    PublisherRegistryMixin,
    TransactionMixin,
    RandomnessMixin,
):
    is_user_client: bool = False
    account_contract_address: Optional[int] = None
    account: Account = None
    full_node_client: FullNodeClient = None

    def __init__(
        self,
        network: str = "devnet",
        account_private_key: Optional[int] = None,
        account_contract_address: Optional[int] = None,
        contract_addresses_config: Optional[ContractAddresses] = None,
        port: Optional[int] = None,
        chain_name: Optional[str] = None,
    ):
        """
        Client for interacting with Pragma on Starknet.
        :param network: Target network for the client.
            Can be a URL string, or one of
            ``"mainnet"``, ``"sepolia"``, ``"pragma_testnet"``, ``"sharingan"`` or ``"devnet"``
        :param account_private_key: Optional private key for requests.  Not necessary if not making network updates
        :param account_contract_address: Optional account contract address.  Not necessary if not making network updates
        :param contract_addresses_config: Optional Contract Addresses for Pragma.
            Will default to the provided network but must be set if using non standard contracts.
        :param port: Optional port to interact with local node. Will default to 5050.
        :param chain_name: A str-representation of the chain if a URL string is given for `network`.
            Must be one of ``"mainnet"``, ``"sepolia"``, ``"pragma_testnet"``, ``"sharingan"`` or ``"devnet"``.
        """

        full_node_client: FullNodeClient = get_client_from_network(network, port=port)
        self.full_node_client = full_node_client
        self.client = full_node_client
        if network.startswith("http") and chain_name is None:
            raise ClientException(
                f"Network provided is a URL: {network} but `chain_name` is not provided."
            )
        self.network = (
            network if not (network.startswith("http") and chain_name) else chain_name
        )
        if account_contract_address and account_private_key:
            self._setup_account_client(
                CHAIN_IDS[self.network],
                account_private_key,
                account_contract_address,
            )

        if not contract_addresses_config:
            contract_addresses_config = CONTRACT_ADDRESSES[self.network]
        self.contract_addresses_config = contract_addresses_config
        self._setup_contracts()

    def _setup_contracts(self):
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

    def full_node_client(self, network, port=None):
        return get_client_from_network(network, port=port)

    async def get_balance(self, account_contract_address, token_address=None):
        client = Account(
            address=account_contract_address,
            client=self.client,
            key_pair=KeyPair.from_private_key(1),
            chain=CHAIN_IDS[self.network],
        )
        balance = await client.get_balance(token_address)
        return balance

    def set_account(self, chain_id, private_key, account_contract_address):
        self._setup_account_client(chain_id, private_key, account_contract_address)

    def _setup_account_client(self, chain_id, private_key, account_contract_address):
        if isinstance(private_key, str):
            private_key = int(private_key, 16)

        self.signer = StarkCurveSigner(
            account_contract_address,
            KeyPair.from_private_key(private_key),
            chain_id,
        )
        self.account = Account(
            address=account_contract_address,
            client=self.client,
            signer=self.signer,
        )
        self.client = self.account.client
        self.account.get_nonce = self._get_nonce  # pylint: disable=protected-access
        self.is_user_client = True
        self.account_contract_address = account_contract_address

    def account_address(self):
        return self.account.address

    def init_stats_contract(
        self,
        stats_contract_address: int,
    ):
        provider = self.account if self.account else self.client
        self.stats = Contract(  # pylint: disable=attribute-defined-outside-init
            address=stats_contract_address,
            abi=ABIS["pragma_SummaryStats"],
            provider=provider,
            cairo_version=1,
        )
