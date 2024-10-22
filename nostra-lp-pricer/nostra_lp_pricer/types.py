from typing import Literal
from pragma_sdk.onchain.abis.abi import get_abi
import json

POOL_ABI =  json.loads(get_abi("pragma_Pool"))

Network = Literal["sepolia", "mainnet"]; 
