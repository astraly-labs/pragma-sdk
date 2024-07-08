import random

from typing import Optional

from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.onchain.types.types import Network
from pragma_sdk.onchain.constants import RPC_URLS


def get_rpc_url(network: Network = "devnet", port: int = 5050) -> str:
    """
    Returns the RPC URL for the given network.
    Will return a random URL in the list if the network is "sepolia" or "mainnet".

    :param network: Network to get the RPC URL for.
    :param port: Port to use for the RPC URL.
    :return: RPC URL.
    """
    match network:
        case str(url) if url.startswith("http"):
            return url
        case "sepolia" | "mainnet":
            urls = RPC_URLS[network]
            return random.choice(urls)
        case "devnet":
            return f"http://127.0.0.1:{port}/rpc"
        case _:
            raise ValueError(f"Unsupported network: {network}")


def get_full_node_client_from_network(network: Network, port: Optional[int] = None):
    """
    Create a new full node client for the passed network/port (rpc url).
    """
    if port is None:
        port = 5050
    return FullNodeClient(node_url=get_rpc_url(network, port=port))
