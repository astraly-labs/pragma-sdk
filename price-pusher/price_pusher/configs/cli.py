import click

from typing import Optional
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.offchain.client import PragmaAPIClient
from pragma_sdk.common.types.client import PragmaClient

from price_pusher.type_aliases import Target, Network


def create_client(
    target: Target,
    network: Network,
    publisher_address: str,
    private_key: str,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> PragmaClient:
    """
    Create the appropriate client based on the target.

    Args:
        target: The target type ('onchain' or 'offchain').
        network: The network type.
        publisher_address: The publisher's address.
        private_key: The private key for the account.
        api_base_url: The API base URL for offchain publishing.
        api_key: The API key for offchain publishing.

    Returns:
        PragmaClient
    """
    if target == "onchain":
        return PragmaOnChainClient(
            network=network,
            account_contract_address=publisher_address,
            account_private_key=private_key,
        )

    elif target == "offchain":
        if not api_key:
            raise click.BadParameter("Argument api-key can't be None if offchain is selected")
        if not api_base_url:
            raise click.BadParameter("Argument api-base-url can't be None if offchain is selected")
        return PragmaAPIClient(
            account_contract_address=publisher_address,
            account_private_key=private_key,
            api_key=api_key,
            api_base_url=api_base_url,
        )
    else:
        raise ValueError(f"Invalid target: {target}")
