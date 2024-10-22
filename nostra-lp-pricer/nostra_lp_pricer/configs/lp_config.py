
from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated


class PoolConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    pool_addresses: Optional[List[str]] = None

    @field_validator("pool_addresses", mode="before")
    def validate_addresses(cls, value: List[str]) -> List[str]:
        # Validate and clean up pool addresses (e.g., remove spaces and make sure they're valid Starknet addresses)
        cleaned_addresses = []
        for address in value:
            address = address.strip().lower()  # Ensure address is in a consistent format
            if len(address) != 66 or not address.startswith("0x"):
                raise ValueError(f"Invalid Starknet address: {address}")
            cleaned_addresses.append(address)
        return cleaned_addresses

    @classmethod
    def from_yaml(cls, path: str) -> "PoolConfig":
        # Read YAML file and parse into PoolConfig instance
        with open(path, "r") as file:
            pool_config = yaml.safe_load(file)
        return cls(**pool_config)

    def get_pool_addresses(self) -> List[str]:
        """
        Get all pool addresses from the configuration.

        Returns:
            List of pool addresses as strings.
        """
        return self.pool_addresses or []



