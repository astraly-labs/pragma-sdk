from typing import Dict, Literal

from pragma.common.types.entry import Entry
from pragma.common.types.types import DataTypes

DurationInSeconds = int

PairId = str
SourceName = str
LatestOrchestratorPairPrices = Dict[PairId, Dict[DataTypes, Dict[SourceName, Entry]]]
LatestOraclePairPrices = Dict[PairId, Dict[DataTypes, Entry]]

HumanReadableId = str

Target = Literal["onchain", "offchain"]
Network = Literal["mainnet", "sepolia"]
