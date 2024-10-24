from typing import Dict, List
from starknet_py.net.models.chains import StarknetChainId

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.onchain.types import ContractAddresses, Network


CHAIN_IDS: Dict[Network, StarknetChainId] = {
    "devnet": StarknetChainId.MAINNET,
    "mainnet": StarknetChainId.MAINNET,
    "sepolia": StarknetChainId.SEPOLIA,
    "pragma_devnet": 6120767554663640178324841317716,
}

CHAIN_ID_TO_NETWORK = {v: k for k, v in CHAIN_IDS.items()}

STARKSCAN_URLS: Dict[Network, str] = {
    "mainnet": "https://starkscan.co",
    "sepolia": "https://sepolia.starkscan.co",
}

RPC_URLS: Dict[Network, List[str]] = {
    "mainnet": [
        "https://starknet-mainnet.public.blastapi.io/rpc/v0_7",
    ],
    "sepolia": [
        "https://starknet-sepolia.public.blastapi.io/rpc/v0_7",
    ],
}

CONTRACT_ADDRESSES = {
    "mainnet": ContractAddresses(
        publisher_registry_address=1035964020232444284030697086969999610062982650901949616270651804992179237909,
        oracle_proxy_addresss=1202089834814778579992154020333959781277480478747022471664051891421849487195,
        summary_stats_address=2090067484320946173645263594661603017833855811144011943422870527090500064765,
    ),
    "sepolia": ContractAddresses(
        publisher_registry_address=764259049439565269590387705502051444787910047543242149334355727309682685773,
        oracle_proxy_addresss=1526899943909931281366530977873767661043021921869578496106478460498705257242,
        summary_stats_address=2384164285657453557205017005077409893704644163574788258484357745200820117852,
    ),
    "pragma_devnet": ContractAddresses(
        publisher_registry_address=int(
            "0x136c93a454973507c96d5933304bc40ce54e61aa1ce88642a2812657ba142a5", 16
        ),
        oracle_proxy_addresss=int(
            "0x56c94b626e02c82bfe871b06181bdc56adcd78f4ce722fe3f7ae6845795d8a8", 16
        ),
        summary_stats_address=int(
            "0x3da8b711d0974aa1ba2564738e74384210a505f8b5deaa3d07045f973d5555c", 16
        ),
    ),
}


RANDOMNESS_REQUEST_EVENT_SELECTOR = (
    "0xe3e1c077138abb6d570b1a7ba425f5479b12f50a78a72be680167d4cf79c48"
)

DERIBIT_MERKLE_FEED_KEY = str_to_felt("DERIBIT_OPTIONS_MERKLE_ROOT")
