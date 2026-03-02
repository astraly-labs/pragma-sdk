from typing import Optional
from dataclasses import dataclass

from pydantic import model_validator
from starknet_py.net.client_models import ResourceBounds


@dataclass(frozen=True)
class ExecutionConfig:
    pagination: int = 40
    max_fee: int = int(1e18)
    enable_strk_fees: bool = True
    l1_resource_bounds: Optional[ResourceBounds] = None
    auto_estimate: bool = False

    @model_validator(mode="after")  # type: ignore[misc]
    def post_root(self) -> None:
        if self.auto_estimate == (self.l1_resource_bounds is not None):
            raise ValueError("Either auto_estimate or l1_resource_bounds must be set")
