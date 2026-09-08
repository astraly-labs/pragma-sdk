from unittest.mock import MagicMock

import yaml

from price_pusher.configs import PriceConfig
from price_pusher.main import _create_listeners

from pragma_sdk.miden.client import STARKNET_PAIR_TO_MIDEN_FAUCET

MIDEN_ONLY_PAIRS = [
    "ZEC/USD",
    "XMR/USD",
    "DASH/USD",
    "XAUT/USD",
    "PAXG/USD",
    "LINK/USD",
    "UNI/USD",
    "AAVE/USD",
    "MORPHO/USD",
]


def _configs(tmp_path):
    raw = [
        {
            "pairs": {"spot": ["BTC/USD", "ETH/USD"]},
            "time_difference": 1800,
            "price_deviation": 0.01,
        },
        {
            "pairs": {"spot": MIDEN_ONLY_PAIRS},
            "time_difference": 1800,
            "price_deviation": 0.01,
            "miden_only": True,
        },
    ]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    return PriceConfig.from_yaml(str(path))


def test_miden_only_defaults_to_false(tmp_path):
    starknet, miden = _configs(tmp_path)
    assert starknet.miden_only is False
    assert miden.miden_only is True


def test_miden_only_group_gets_no_starknet_listener(tmp_path):
    configs = _configs(tmp_path)
    listeners = _create_listeners(configs, MagicMock())
    assert len(listeners) == 1
    listened = {str(p) for p in listeners[0].price_config.pairs.spot}
    assert listened == {"BTC/USD", "ETH/USD"}


def test_miden_only_pairs_are_mapped_to_faucets():
    faucets = [STARKNET_PAIR_TO_MIDEN_FAUCET[p] for p in MIDEN_ONLY_PAIRS]
    assert faucets == [f"{i}:0" for i in range(6, 15)]
    assert len(set(STARKNET_PAIR_TO_MIDEN_FAUCET.values())) == len(
        STARKNET_PAIR_TO_MIDEN_FAUCET
    )


def test_mainnet_config_miden_group_matches_faucet_mapping():
    configs = PriceConfig.from_yaml("../infra/price-pusher/config/config.mainnet.yaml")
    miden_groups = [c for c in configs if c.miden_only]
    assert len(miden_groups) == 1
    pairs = {str(p) for p in miden_groups[0].pairs.spot}
    assert pairs == set(MIDEN_ONLY_PAIRS)
    assert pairs <= STARKNET_PAIR_TO_MIDEN_FAUCET.keys()
