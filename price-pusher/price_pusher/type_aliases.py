from typing import Dict, Literal

from pragma.common.types.entry import Entry
from pragma.common.assets import AssetType

DurationInSeconds = int

PairId = str
SourceName = str
LatestOrchestratorPairPrices = Dict[PairId, Dict[AssetType, Dict[SourceName, Entry]]]
LatestOraclePairPrices = Dict[PairId, Dict[AssetType, Entry]]

HumanReadableId = str

Target = Literal["onchain", "offchain"]
Network = Literal["mainnet", "sepolia"]
