from typing import Optional
from dataclasses import dataclass

from pydantic import model_validator
from starknet_py.net.client_models import ResourceBoundsMapping


@dataclass(frozen=True)
class ExecutionConfig:
    pagination: int = 40
    # Kept for CLI compatibility; ignored since starknet.py 0.26 removed v1
    # transactions (every invoke is a v3 transaction paid in STRK).
    max_fee: int = int(1e18)
    enable_strk_fees: bool = True
    # Explicit L1/L2 resource bounds for v3 invokes; None means auto_estimate.
    l1_resource_bounds: Optional[ResourceBoundsMapping] = None
    auto_estimate: bool = False
    # 0.14+ fee market: estimate the tip from the pre_confirmed block instead
    # of sending tip=0.
    auto_estimate_tip: bool = False

    @model_validator(mode="after")  # type: ignore[misc]
    def post_root(self) -> None:
        if self.auto_estimate == (self.l1_resource_bounds is not None):
            raise ValueError("Either auto_estimate or l1_resource_bounds must be set")
