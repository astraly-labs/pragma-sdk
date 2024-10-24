import random
import requests
import copy

from requests.exceptions import RequestException
from typing import List, Optional

from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.onchain.types.types import Network
from pragma_sdk.onchain.constants import RPC_URLS


def pick_random_rpc(network: str, urls: List[str], timeout: int = 5) -> str:
    """
    Picks a random RPC endpoint from the list and verifies it's working.
    Tests each RPC with a spec version request until finding a working one.
    """
    available_urls = copy.copy(urls)

    while available_urls:
        url = random.choice(available_urls)
        available_urls.remove(url)

        headers = {"Content-Type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": 0, "method": "starknet_specVersion"}
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout
            )
            if (
                response.status_code == 200
                and response.json().get("result")
                and not response.json().get("error")
            ):
                # If the RPC works, return it!
                return url

        except RequestException:
            continue

    # If we don't have any working RPC, error out.
    raise ValueError(
        f"No working RPC endpoints found for network: {network}. "
        f"Tried {len(urls)} endpoints."
    )


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
            return pick_random_rpc(network, RPC_URLS[network])
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
