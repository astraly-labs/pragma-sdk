from .binance import BinanceFetcher
from .bitstamp import BitstampFetcher
from .bybit import BybitFetcher
from .coinbase import CoinbaseFetcher
from .defillama import DefillamaFetcher
from .gecko import GeckoTerminalFetcher
from .huobi import HuobiFetcher
from .index import IndexFetcher
from .indexcoop import IndexCoopFetcher
from .kucoin import KucoinFetcher
from .okx import OkxFetcher
from .propeller import PropellerFetcher
from .starknetamm import StarknetAMMFetcher
from .mexc import MEXCFetcher
from .gateio import GateioFetcher

__all__ = [
    BinanceFetcher,
    BitstampFetcher,
    BybitFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    IndexFetcher,
    IndexCoopFetcher,
    KucoinFetcher,
    OkxFetcher,
    PropellerFetcher,
    StarknetAMMFetcher,
    MEXCFetcher,
    GateioFetcher,
]
