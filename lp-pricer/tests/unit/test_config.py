import pytest
import yaml

from typing import List

from lp_pricer.configs.pools_config import PoolsConfig


@pytest.fixture
def sample_yaml_file(tmp_path):
    """Create a temporary YAML file with test data."""
    content = {
        "pool_addresses": [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
        ]
    }
    yaml_file = tmp_path / "test_pools.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(content, f)
    return yaml_file


@pytest.fixture
def invalid_yaml_file(tmp_path):
    """Create a temporary YAML file with invalid data."""
    content = {"pool_addresses": ["invalid_address", "0xNOTHEX"]}
    yaml_file = tmp_path / "invalid_pools.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(content, f)
    return yaml_file


def test_pools_config_from_yaml(sample_yaml_file):
    """Test successful creation of PoolsConfig from YAML file."""
    config = PoolsConfig.from_yaml(str(sample_yaml_file))
    assert isinstance(config, PoolsConfig)
    assert len(config.pool_addresses) == 2
    assert config.pool_addresses[0] == "0x1234567890abcdef1234567890abcdef12345678"
    assert config.pool_addresses[1] == "0xabcdef1234567890abcdef1234567890abcdef12"


def test_get_all_pools(sample_yaml_file):
    """Test conversion of hex addresses to integers."""
    config = PoolsConfig.from_yaml(str(sample_yaml_file))
    pools = config.get_all_pools()

    assert isinstance(pools, List)
    assert len(pools) == 2
    assert pools[0] == int("1234567890abcdef1234567890abcdef12345678", 16)
    assert pools[1] == int("abcdef1234567890abcdef1234567890abcdef12", 16)


def test_invalid_hex_addresses(invalid_yaml_file):
    """Test handling of invalid hex addresses."""
    config = PoolsConfig.from_yaml(str(invalid_yaml_file))
    with pytest.raises(ValueError):
        config.get_all_pools()


def test_file_not_found():
    """Test handling of non-existent YAML file."""
    with pytest.raises(FileNotFoundError):
        PoolsConfig.from_yaml("nonexistent_file.yaml")


def test_invalid_yaml_format(tmp_path):
    """Test handling of malformed YAML file."""
    invalid_yaml = tmp_path / "invalid.yaml"
    with open(invalid_yaml, "w") as f:
        f.write("invalid: yaml: content: :")

    with pytest.raises(yaml.YAMLError):
        PoolsConfig.from_yaml(str(invalid_yaml))


def test_empty_pool_addresses(tmp_path):
    """Test handling of empty pool addresses list."""
    content = {"pool_addresses": []}
    yaml_file = tmp_path / "empty_pools.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(content, f)

    config = PoolsConfig.from_yaml(str(yaml_file))
    assert len(config.get_all_pools()) == 0
