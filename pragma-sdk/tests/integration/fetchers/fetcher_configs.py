from pragma_sdk.common.types.entry import FutureEntry, SpotEntry
from pragma_sdk.common.fetchers.fetchers import (
    DefillamaFetcher,
    BitstampFetcher,
    CoinbaseFetcher,
    OkxFetcher,
    EkuboFetcher,
    PropellerFetcher,
    GeckoTerminalFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import (
    ByBitFutureFetcher,
    OkxFutureFetcher,
)
from tests.integration.constants import MOCK_DIR

PUBLISHER_NAME = "TEST_PUBLISHER"


FETCHER_CONFIGS = {
    "DefillamaFetcher": {
        "mock_file": MOCK_DIR / "responses" / "defillama.json",
        "fetcher_class": DefillamaFetcher,
        "name": "Defillama",
        "expected_result": [
            SpotEntry("BTC/USD", 2604800000000, 12345, "DEFILLAMA", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164507000000, 12345, "DEFILLAMA", PUBLISHER_NAME),
        ],
    },
    "BitstampFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bitstamp.json",
        "fetcher_class": BitstampFetcher,
        "name": "Bitstamp",
        "expected_result": [
            SpotEntry("BTC/USD", 2602100000000, 12345, "BITSTAMP", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164250000000, 12345, "BITSTAMP", PUBLISHER_NAME),
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
                12345,
                "OKX",
                PUBLISHER_NAME,
                volume=18382.3898,
            ),
            SpotEntry(
                "ETH/USD",
                167372000000,
                12345,
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
                12345,
                "BYBIT",
                PUBLISHER_NAME,
                0,
                volume=float(421181110),
            ),
            FutureEntry(
                "ETH/USD",
                164025000000,
                12345,
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
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=274,
                expiry_timestamp=1695369600000,
            ),
            FutureEntry(
                pair_id="BTC/USD",
                price=2666120000000,
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=1020,
                expiry_timestamp=1695974400000,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159390000000,
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=2276,
                expiry_timestamp=1695369600000,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159092000000,
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=6178,
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
                volume=1264558,
            ),
            SpotEntry(
                "WBTC/USD",
                2580468000000,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=90241580,
            ),
        ],
    },
    "EkuboFetcher": {
        "mock_file": MOCK_DIR / "responses" / "starknet_amm.json",
        "fetcher_class": EkuboFetcher,
        "name": "Starknet",
        "expected_result": [
            SpotEntry(
                "LUSD/USD",
                1001354537000,
                12345,
                "EKUBO",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "WBTC/USD",
                5763275533000,
                12345,
                "EKUBO",
                PUBLISHER_NAME,
                volume=0,
            ),
        ],
    },
}
