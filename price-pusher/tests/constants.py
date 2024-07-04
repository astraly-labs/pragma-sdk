from pragma.common.configs.asset_config import AssetConfig
from pragma.common.types.pair import Pair


BTC_USD_PAIR: Pair = AssetConfig.try_get_pair_from_tickers("BTC", "USD")
