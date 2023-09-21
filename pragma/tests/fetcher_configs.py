from pragma.core.entry import FutureEntry, SpotEntry
from pragma.publisher.fetchers.ascendex import AscendexFetcher
from pragma.publisher.fetchers.bitstamp import BitstampFetcher
from pragma.publisher.fetchers.cex import CexFetcher
from pragma.publisher.fetchers.coinbase import CoinbaseFetcher
from pragma.publisher.fetchers.defillama import DefillamaFetcher
from pragma.publisher.fetchers.gecko import GeckoTerminalFetcher
from pragma.publisher.fetchers.kaiko import KaikoFetcher
from pragma.publisher.fetchers.okx import OkxFetcher
from pragma.publisher.future_fetchers.bybit import ByBitFutureFetcher
from pragma.publisher.future_fetchers.okx import OkxFutureFetcher
from pragma.tests.constants import MOCK_DIR

PUBLISHER_NAME = "TEST_PUBLISHER"


FETCHER_CONFIGS = {
    "CexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "cex.json",
        "fetcher_class": CexFetcher,
        "name": "CEX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601210000000,
                1692717096,
                "CEX",
                PUBLISHER_NAME,
                volume=1.81043893,
            ),
            SpotEntry(
                "ETH/USD",
                163921000000,
                1692724899,
                "CEX",
                PUBLISHER_NAME,
                volume=56.54796900,
            ),
        ],
    },
    "DefillamaFetcher": {
        "mock_file": MOCK_DIR / "responses" / "defillama.json",
        "fetcher_class": DefillamaFetcher,
        "name": "Defillama",
        "expected_result": [
            SpotEntry(
                "BTC/USD", 2604800000000, 1692779346, "DEFILLAMA", PUBLISHER_NAME
            ),
            SpotEntry("ETH/USD", 164507000000, 1692779707, "DEFILLAMA", PUBLISHER_NAME),
        ],
    },
    "BitstampFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bitstamp.json",
        "fetcher_class": BitstampFetcher,
        "name": "Bitstamp",
        "expected_result": [
            SpotEntry("BTC/USD", 2602100000000, 1692781034, "BITSTAMP", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164250000000, 1692780986, "BITSTAMP", PUBLISHER_NAME),
        ],
    },
    "CoinbaseFetcher": {
        "mock_file": MOCK_DIR / "responses" / "coinbase.json",
        "fetcher_class": CoinbaseFetcher,
        "name": "Coinbase",
        "expected_result": [
            SpotEntry("BTC/USD", 2602820500003, 12345, "COINBASE", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164399499999, 12345, "COINBASE", PUBLISHER_NAME),
        ],
    },
    "AscendexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "ascendex.json",
        "fetcher_class": AscendexFetcher,
        "name": "Ascendex",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2602650000000,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=9.7894,
            ),
            SpotEntry(
                "ETH/USD",
                164369999999,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=123.188,
            ),
        ],
    },
    "OkxFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx.json",
        "fetcher_class": OkxFetcher,
        "name": "OKX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2640240000000,
                1692829724,
                "OKX",
                PUBLISHER_NAME,
                volume=18382.3898,
            ),
            SpotEntry(
                "ETH/USD",
                167372000000,
                1692829751,
                "OKX",
                PUBLISHER_NAME,
                volume=185341.3646,
            ),
        ],
    },
    "KaikoFetcher": {
        "mock_file": MOCK_DIR / "responses" / "kaiko.json",
        "fetcher_class": KaikoFetcher,
        "name": "Kaiko",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601601000000,
                1692782303,
                "KAIKO",
                PUBLISHER_NAME,
                volume=0.00414884,
            ),
            SpotEntry(
                "ETH/USD",
                164315580431,
                1692782453,
                "KAIKO",
                PUBLISHER_NAME,
                volume=45.04710943999999,
            ),
        ],
    },
}

FUTURE_FETCHER_CONFIGS = {
    "ByBitFutureFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bybit_future.json",
        "fetcher_class": ByBitFutureFetcher,
        "name": "BYBIT",
        "expected_result": [
            FutureEntry(
                "BTC/USD",
                2589900000000,
                1692982428,
                "BYBIT",
                PUBLISHER_NAME,
                0,
                volume=float(421181110),
            ),
            FutureEntry(
                "ETH/USD",
                164025000000,
                1692982480,
                "BYBIT",
                PUBLISHER_NAME,
                0,
                volume=float(56108213),
            ),
        ],
    },
    "OkxFutureFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx_future" / "ticker.json",
        "fetcher_class": OkxFutureFetcher,
        "name": "OKX",
        "other_mock_fns": [
            {
                "format_expiry_timestamp_url": {
                    "kwargs": {
                        "BTC": {"id": "BTC-USD-230922"},
                        "ETH": {"id": "ETH-USD-230922"},
                    },
                    "mock_file": MOCK_DIR
                    / "responses"
                    / "okx_future"
                    / "timestamp_230922.json",
                }
            },
            {
                "format_expiry_timestamp_url": {
                    "kwargs": {
                        "BTC": {"id": "BTC-USD-230929"},
                        "ETH": {"id": "ETH-USD-230929"},
                    },
                    "mock_file": MOCK_DIR
                    / "responses"
                    / "okx_future"
                    / "timestamp_230929.json",
                }
            },
        ],
        "expected_result": [
            FutureEntry(
                pair_id="BTC/USD",
                price=2664490000000,
                timestamp=1695293953,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=73224927992200000700416,
                expiry_timestamp=1695369600000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="BTC/USD",
                price=2666120000000,
                timestamp=1695293953,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=271979672734799985901568,
                expiry_timestamp=1695974400000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159390000000,
                timestamp=1695293986,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=36278392896900000907264,
                expiry_timestamp=1695369600000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159092000000,
                timestamp=1695293987,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=98295299247559996866560,
                expiry_timestamp=1695974400000,
                autoscale_volume=False,
            ),
        ],
    },
}

ONCHAIN_FETCHER_CONFIGS = {
    "GeckoTerminalFetcher": {
        "mock_file": MOCK_DIR / "responses" / "gecko.json",
        "fetcher_class": GeckoTerminalFetcher,
        "name": "GeckoTerminal",
        "expected_result": [
            SpotEntry(
                "R/USD",
                98898157,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=1264558.5626824791626951720608214185,
            ),
            SpotEntry(
                "WBTC/USD",
                2580468000000,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=90241580.528001091809493184,
            ),
        ],
    },
}
