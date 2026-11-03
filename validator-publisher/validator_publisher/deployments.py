"""
Contracts of the validator publishing pilot (DP-PRA-381, scope C), fixed per
release: an operator never points the client at other contracts by mistake.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from pragma_sdk.onchain.types import ContractAddresses

PILOT_PAIRS: Tuple[str, ...] = (
    "BTC/USD",
    "ETH/USD",
    "STRK/USD",
    "USDC/USD",
    "USDT/USD",
)

STRK_TOKEN = 0x04718F5A0FC34CC1AF16A1CDEE98FFB20C31F5CD61D6AB07201858F4287C938D

STAKING_CONTRACTS: Dict[str, int] = {
    "mainnet": 0x00CA1702E64C81D9A07B86BD2C540188D92A2C73CF5CC0E508D949015E7E84A7,
    "sepolia": 0x03745AB04A431FC02871A139BE6B93D9260B0FF3E779AD9C8B377183B23109F1,
}


@dataclass(frozen=True)
class PilotDeployment:
    oracle: int
    validator_registry: int

    def contract_addresses(self) -> ContractAddresses:
        # summary stats are not part of the pilot
        return ContractAddresses(
            publisher_registry_address=self.validator_registry,
            oracle_proxy_addresss=self.oracle,
            summary_stats_address=0,
        )


# Filled in by the release that ships each deployment.
PILOT_DEPLOYMENTS: Dict[str, Optional[PilotDeployment]] = {
    "sepolia": None,
    "mainnet": None,
}


def get_deployment(network: str) -> PilotDeployment:
    deployment = PILOT_DEPLOYMENTS.get(network)
    if deployment is None:
        raise ValueError(
            f"The pilot contracts are not deployed on {network} in this release"
        )
    return deployment
