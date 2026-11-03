from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from price_pusher.configs.price_config import PriceConfig

from validator_publisher.deployments import (
    PILOT_PAIRS,
    PilotDeployment,
    get_deployment,
)

SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1,)
PRIVATE_KEY_PREFIXES = ("env:", "keystore:", "aws:", "gcp:", "plain:")


def _hex_address(value: str) -> str:
    if not isinstance(value, str) or not value.lower().startswith("0x"):
        raise ValueError("must be a 0x-prefixed hex address")
    as_int = int(value, 16)
    if as_int == 0 or as_int >= 2**251:
        raise ValueError("is not a Starknet contract address")
    return hex(as_int)


class ContractsOverride(BaseModel):
    """Non-release contracts, for testing a deployment before it ships."""

    model_config = ConfigDict(extra="forbid")

    oracle: str
    validator_registry: str

    @field_validator("oracle", "validator_registry")
    @classmethod
    def _address(cls, value: str) -> str:
        return _hex_address(value)


class ValidatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    network: Literal["mainnet", "sepolia"]
    rpc_url: str
    staker_address: str
    oracle_signer_address: str
    private_key: str
    pairs: List[str] = Field(default_factory=lambda: list(PILOT_PAIRS))
    time_difference: int = Field(default=1800, gt=0)
    price_deviation: float = Field(default=0.01, gt=0)
    health_port: int = 8080
    min_signer_balance_strk: float = Field(default=50, ge=0)
    evm_rpc_urls: List[str] = Field(default_factory=list)
    contracts: Optional[ContractsOverride] = None

    @field_validator("schema_version")
    @classmethod
    def _schema(cls, value: int) -> int:
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {value} is not supported by this release "
                f"(supported: {', '.join(map(str, SUPPORTED_SCHEMA_VERSIONS))})"
            )
        return value

    @field_validator("rpc_url")
    @classmethod
    def _rpc(cls, value: str) -> str:
        if not value.startswith("http"):
            raise ValueError("must be the http(s) JSON-RPC URL of your node")
        return value

    @field_validator("staker_address", "oracle_signer_address")
    @classmethod
    def _address(cls, value: str) -> str:
        return _hex_address(value)

    @field_validator("private_key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not value.startswith(PRIVATE_KEY_PREFIXES):
            raise ValueError(
                f"must start with one of {', '.join(PRIVATE_KEY_PREFIXES)}"
            )
        return value

    @field_validator("pairs")
    @classmethod
    def _pairs(cls, value: List[str]) -> List[str]:
        pairs = [p.replace(" ", "").upper() for p in value]
        unknown = sorted(set(pairs) - set(PILOT_PAIRS))
        if unknown:
            raise ValueError(
                f"{', '.join(unknown)} not in the pilot pairs ({', '.join(PILOT_PAIRS)})"
            )
        if not pairs:
            raise ValueError("at least one pilot pair is required")
        return sorted(set(pairs))

    @model_validator(mode="after")
    def _key_separation(self) -> "ValidatorConfig":
        if self.oracle_signer_address == self.staker_address:
            raise ValueError("the oracle signer must not be the staker address")
        return self

    @classmethod
    def from_yaml(cls, path: str) -> "ValidatorConfig":
        with open(path, "r") as file:
            return cls(**(yaml.safe_load(file) or {}))

    def deployment(self) -> PilotDeployment:
        if self.contracts is not None:
            return PilotDeployment(
                oracle=int(self.contracts.oracle, 16),
                validator_registry=int(self.contracts.validator_registry, 16),
            )
        return get_deployment(self.network)

    def price_config(self) -> PriceConfig:
        return PriceConfig(
            pairs={"spot": self.pairs},
            time_difference=self.time_difference,
            price_deviation=self.price_deviation,
        )
