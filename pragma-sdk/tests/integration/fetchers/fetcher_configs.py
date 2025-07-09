from pragma_sdk.common.types.entry import FutureEntry, SpotEntry
from pragma_sdk.common.fetchers.fetchers import (
    DefillamaFetcher,
    BitstampFetcher,
    CoinbaseFetcher,
    OkxFetcher,
    EkuboFetcher,
    GeckoTerminalFetcher,
    DexscreenerFetcher,
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
        "expected_result": [
            FutureEntry(
                pair_id="BTC/USD",
                price=2640240000000,
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=18382.3898,
                expiry_timestamp=0,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=167372000000,
                timestamp=12345,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=185341.3646,
                expiry_timestamp=0,
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
    "DexscreenerFetcher": {
        "mock_file": MOCK_DIR / "responses" / "dexscreener.json",
        "fetcher_class": DexscreenerFetcher,
        "name": "Dexscreener",
        "expected_result": [
            SpotEntry(
                "LUSD/USD",
                56845000000,
                12345,
                "DEXSCREENER",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "WBTC/USD",
                56845000000,
                12345,
                "DEXSCREENER",
                PUBLISHER_NAME,
                volume=0,
            ),
        ],
    },
}

RPC_FETCHER_CONFIGS = {
    "EkuboFetcher": {
        "mock_file": MOCK_DIR / "responses" / "ekubo.json",
        "fetcher_class": EkuboFetcher,
        "name": "Ekubo",
        "expected_result": [
            SpotEntry(
                "LUSD/USD",
                5522096,
                12345,
                "EKUBO",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "WBTC/USD",
                6664870762713,
                12345,
                "EKUBO",
                PUBLISHER_NAME,
                volume=0,
            ),
        ],
    },
}
