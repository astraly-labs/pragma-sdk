
from pragma_sdk.onchain.utils import get_full_node_client_from_network,get_rpc_url
from nostra_lp_pricer.types import Network, POOL_ABI
from starknet_py.net.account.account import Account
from starknet_py.net.models import StarknetChainId
import logging
import os
from typing import Optional
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner
from starknet_py.contract import Contract


logger = logging.getLogger(__name__)
NETWORKS = {
    "mainnet": {
        "name": "mainnet",
        "rpc_url": "https://starknet-mainnet.public.blastapi.io/rpc/v0_7",
    },
    "sepolia": {
        "name": "sepolia",
        "explorer_url": "https://sepolia.starkscan.co/",
        "rpc_url": "https://starknet-sepolia.public.blastapi.io/rpc/v0_7",
    },
    "devnet": {
        "name": "devnet",
        "explorer_url": "https://devnet.starkscan.co",
        "rpc_url": "http://127.0.0.1:5050/rpc",
    },
}

NETWORK = NETWORKS[os.getenv("STARKNET_NETWORK", "sepolia")]
NETWORK["account_address"] = os.environ.get(
    f"{NETWORK['name'].upper()}_ACCOUNT_ADDRESS"
)
if NETWORK["account_address"] is None:
    logger.warning(
        f"⚠️ {NETWORK['name'].upper()}_ACCOUNT_ADDRESS not set, defaulting to ACCOUNT_ADDRESS"
    )
    NETWORK["account_address"] = os.getenv("ACCOUNT_ADDRESS")
NETWORK["private_key"] = os.environ.get(f"{NETWORK['name'].upper()}_PRIVATE_KEY")
if NETWORK["private_key"] is None:
    logger.warning(
        f"⚠️  {NETWORK['name'].upper()}_PRIVATE_KEY not set, defaulting to PRIVATE_KEY"
    )
    NETWORK["private_key"] = os.getenv("PRIVATE_KEY")
if NETWORK["name"] == "mainnet":
    NETWORK["chain_id"] = StarknetChainId.MAINNET
else:
    NETWORK["chain_id"] = StarknetChainId.SEPOLIA


def get_account(network: Network,address: Optional[int]=None, private_key: Optional[int]=None) -> Account: 
    client = get_full_node_client_from_network(network)
    address = address or  NETWORK["account_address"]
    private_key = private_key or NETWORK["private_key"]

    signer = StarkCurveSigner(
       address,
        KeyPair.from_private_key(private_key),
        NETWORK["chain_id"],
        )
    return Account(
        address= NETWORK["account_address"],
        client=client,
        signer=signer,
        )

def get_contract(network: Network,contract_name: int, abi: dict,  cairo_version: Optional[int] = 1,address: Optional[int]=None, private_key: Optional[int]=None ) -> Contract:
    provider = get_account(network, address, private_key)
    return Contract(
            address=contract_name,
            abi=abi,
            provider=provider,
            cairo_version=cairo_version,
        )