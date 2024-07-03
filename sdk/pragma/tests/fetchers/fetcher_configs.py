from pragma.common.types.entry import FutureEntry, SpotEntry
from pragma.common.fetchers.fetchers import (
    DefillamaFetcher,
    BitstampFetcher,
    CoinbaseFetcher,
    OkxFetcher,
    StarknetAMMFetcher,
    PropellerFetcher,
    GeckoTerminalFetcher,
)
from pragma.common.fetchers.future_fetchers import (
    ByBitFutureFetcher,
    OkxFutureFetcher,
)
from pragma.tests.constants import MOCK_DIR

PUBLISHER_NAME = "TEST_PUBLISHER"


FETCHER_CONFIGS = {
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
}


INDEX_FETCHER_CONFIGS = {
    "DefillamaFetcher": {
        "mock_file": MOCK_DIR / "responses" / "defillama.json",
        "fetcher_class": DefillamaFetcher,
        "name": "Defillama",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(2604800000000 * 0.5 + 164507000000 * 0.5),
            12345,
            "DEFILLAMA",
            PUBLISHER_NAME,
        ),
    },
    "BitstampFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bitstamp.json",
        "fetcher_class": BitstampFetcher,
        "name": "Bitstamp",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(2602100000000 * 0.5 + 164250000000 * 0.5),
            12345,
            "BITSTAMP",
            PUBLISHER_NAME,
        ),
    },
    "CoinbaseFetcher": {
        "mock_file": MOCK_DIR / "responses" / "coinbase.json",
        "fetcher_class": CoinbaseFetcher,
        "name": "Coinbase",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(2602820500003 * 0.5 + 164399499999 * 0.5),
            12345,
            "COINBASE",
            PUBLISHER_NAME,
        ),
    },
    "OkxFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx.json",
        "fetcher_class": OkxFetcher,
        "name": "OKX",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(2640240000000 * 0.5 + 167372000000 * 0.5),
            12345,
            "OKX",
            PUBLISHER_NAME,
        ),
    },
    "PropellerFetcher": {
        "mock_file": MOCK_DIR / "responses" / "propeller.json",
        "fetcher_class": PropellerFetcher,
        "name": "PROPELLER",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(4891252302700 * 0.5 + 0.5 * 262209039700),
            12345,
            "PROPELLER",
            PUBLISHER_NAME,
        ),
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
                        "BTC": {"instrument_id": "BTC-USD-230922"},
                        "ETH": {"instrument_id": "ETH-USD-230922"},
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
                        "BTC": {"instrument_id": "BTC-USD-230929"},
                        "ETH": {"instrument_id": "ETH-USD-230929"},
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
            ),
            FutureEntry(
                pair_id="BTC/USD",
                price=2666120000000,
                timestamp=1695293953,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=271979672734799985901568,
                expiry_timestamp=1695974400000,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159390000000,
                timestamp=1695293986,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=36278392896900000907264,
                expiry_timestamp=1695369600000,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159092000000,
                timestamp=1695293987,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=98295299247559996866560,
                expiry_timestamp=1695974400000,
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
                "LUSD/USD",
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
    "StarknetAMMFetcher": {
        "mock_file": MOCK_DIR / "responses" / "starknet_amm.json",
        "fetcher_class": StarknetAMMFetcher,
        "name": "Starknet",
        "expected_result": [
            SpotEntry(
                "ETH/USDC",
                10013545370000000000000,
                12345,
                "STARKNET",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "DAI/USDC",
                12095527530000000000,
                12345,
                "STARKNET",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "WBTC/USDC",
                66247877310000000,
                12345,
                "STARKNET",
                PUBLISHER_NAME,
                volume=0,
            ),
        ],
    },
}
