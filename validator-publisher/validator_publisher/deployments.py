"""
Contracts of the validator publishing pilot (DP-PRA-381, scope C), fixed per
release: an operator never points the client at other contracts by mistake.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.onchain.types import ContractAddresses

_CEX = frozenset(
    {"BINANCE", "BITGET", "BYBIT", "GATEIO", "HUOBI", "KUCOIN", "LBANK", "OKX"}
)

# Markets that quote each pair, as the operators' fetchers return them. The
# source of an entry is a label its publisher writes and the chain cannot
# verify, so the feed only counts these: a label the registry allows on no
# real market of the pair is free for anyone to fill.
PAIR_SOURCES: Dict[str, FrozenSet[str]] = {
    "BTC/USD": _CEX | {"BITSTAMP"},
    "ETH/USD": _CEX | {"BITSTAMP", "EKUBO"},
    "STRK/USD": _CEX | {"EKUBO"},
    "USDC/USD": _CEX | {"BITSTAMP"},
    "USDT/USD": frozenset({"BINANCE", "BITGET", "BITSTAMP", "BYBIT", "EKUBO", "UPBIT"}),
}

PILOT_PAIRS: Tuple[str, ...] = tuple(PAIR_SOURCES)


def pair_sources(pair: str) -> FrozenSet[int]:
    return frozenset(str_to_felt(s) for s in PAIR_SOURCES.get(pair, ()))


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
    # pragma-oracle deployments/sepolia/validator_pilot.json, 2026-11-04
    "sepolia": PilotDeployment(
        oracle=0x0417C6079B630414C223B2567C3D786C2ABE9FA189E11C8CB3455F602044F658,
        validator_registry=0x056F2C0121BBD89983DE8E6A300966115C7B7692A1BA38546D6CC2036B92AB58,
    ),
    "mainnet": None,
}


def get_deployment(network: str) -> PilotDeployment:
    deployment = PILOT_DEPLOYMENTS.get(network)
    if deployment is None:
        raise ValueError(
            f"The pilot contracts are not deployed on {network} in this release"
        )
    return deployment
