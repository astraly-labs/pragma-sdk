from typing import Literal, Tuple
from pragma_sdk.onchain.abis.abi import get_abi
import json

POOL_ABI =  json.loads(get_abi("pragma_Pool"))
PRICER_ABI = json.loads(get_abi("pragma_LightPoolRegistry"))
FETCH_INTERVAL: int= 10 # Fetching total supply and reserve every 10s
PUSH_INTERVAL: int = 10 # Pushing the price every 10s
TARGET_DECIMALS: int = 18
PERIOD : int = 600 # 10 minutes(operations are done over a 10minutes range)
ORACLE_ADDRESSES = {
    "sepolia": "0x36031daa264c24520b11d93af622c848b2499b66b41d611bac95e13cfca131a", 
    "mainnet": "0x02a85bd616f912537c50a49a4076db02c00b29b2cdc8a197ce92ed1837fa875b"
}
Network = Literal["sepolia", "mainnet"]
Reserves = Tuple[int, int]
