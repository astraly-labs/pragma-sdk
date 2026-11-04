import pytest
import yaml

from pydantic import ValidationError

from validator_publisher.config import ValidatorConfig
from validator_publisher.deployments import PILOT_PAIRS

STAKER = "0x077d4b4e7ae321aabd0a5a7322108635fcbd0cd746f9ae217b8ea00363494b65"
SIGNER = "0x5161"


def _config(**overrides) -> dict:
    config = {
        "schema_version": 1,
        "network": "sepolia",
        "rpc_url": "http://pathfinder:9545/rpc/v0_10",
        "staker_address": STAKER,
        "oracle_signer_address": SIGNER,
        "private_key": "env:ORACLE_SIGNER_PRIVATE_KEY",
    }
    config.update(overrides)
    return config


def test_defaults_publish_every_pilot_pair():
    config = ValidatorConfig(**_config())
    assert config.pairs == sorted(PILOT_PAIRS)
    assert config.staker_address == hex(int(STAKER, 16))


def test_unknown_schema_version_is_refused():
    with pytest.raises(ValidationError, match="schema_version 2"):
        ValidatorConfig(**_config(schema_version=2))


def test_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        ValidatorConfig(**_config(oracle_address="0x1"))


def test_pairs_outside_the_pilot_are_refused():
    with pytest.raises(ValidationError, match="DOGE/USD"):
        ValidatorConfig(**_config(pairs=["BTC/USD", "DOGE/USD"]))


def test_signer_cannot_be_the_staker():
    with pytest.raises(ValidationError, match="must not be the staker"):
        ValidatorConfig(**_config(oracle_signer_address=STAKER))


@pytest.mark.parametrize("key", ["0xabc", "file:/tmp/key"])
def test_private_key_needs_a_source_prefix(key):
    with pytest.raises(ValidationError, match="must start with"):
        ValidatorConfig(**_config(private_key=key))


def test_rpc_url_must_be_http():
    with pytest.raises(ValidationError, match="http"):
        ValidatorConfig(**_config(rpc_url="ws://node:9545"))


def test_release_pins_the_sepolia_pilot():
    addresses = ValidatorConfig(**_config()).deployment().contract_addresses()
    assert addresses.oracle_proxy_addresss == int(
        "0x0417c6079b630414c223b2567c3d786c2abe9fa189e11c8cb3455f602044f658", 16
    )


def test_release_has_no_mainnet_deployment_yet():
    with pytest.raises(ValueError, match="not deployed on mainnet"):
        ValidatorConfig(**_config(network="mainnet")).deployment()


def test_contracts_override_for_testing():
    config = ValidatorConfig(
        **_config(contracts={"oracle": "0x111", "validator_registry": "0x222"})
    )
    addresses = config.deployment().contract_addresses()
    assert addresses.oracle_proxy_addresss == 0x111
    assert addresses.publisher_registry_address == 0x222


def test_price_config_follows_the_config():
    price_config = ValidatorConfig(
        **_config(pairs=["BTC/USD"], time_difference=600)
    ).price_config()
    assert [str(p) for p in price_config.pairs.spot] == ["BTC/USD"]
    assert price_config.time_difference == 600


def test_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(_config()))
    assert ValidatorConfig.from_yaml(str(path)).network == "sepolia"
