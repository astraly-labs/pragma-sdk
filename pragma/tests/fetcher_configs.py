# pylint: disable=wildcard-import, unused-wildcard-import
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.publisher.fetchers import *
from pragma.publisher.future_fetchers import *
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
    "TheGraphFetcher": {
        "mock_file": MOCK_DIR / "responses" / "thegraph.json",
        "fetcher_class": TheGraphFetcher,
        "name": "TheGraph",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                3459885191309,
                12345,
                "THEGRAPH",
                PUBLISHER_NAME,
                volume=13263948239.39806410965943312664704,
            ),
            SpotEntry(
                "ETH/USD",
                180043642780,
                12345,
                "THEGRAPH",
                PUBLISHER_NAME,
                volume=406618849947.3046337346962943997025,
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
    "PropellerFetcher": {
        "mock_file": MOCK_DIR / "responses" / "propeller.json",
        "fetcher_class": PropellerFetcher,
        "name": "PROPELLER",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                4891252302700,
                12345,
                "PROPELLER",
                PUBLISHER_NAME,
            ),
            SpotEntry(
                "ETH/USD",
                262209039700,
                12345,
                "PROPELLER",
                PUBLISHER_NAME,
            ),
        ],
    },
    "IndexCoopFetcher": {
        "mock_file": MOCK_DIR / "responses" / "indexcoop.json",
        "fetcher_class": IndexCoopFetcher,
        "name": "IndexCoop",
        "expected_result": [
            SpotEntry(
                "DPI",
                13628454601,
                12345,
                "INDEXCOOP",
                PUBLISHER_NAME,
                volume=6454312441521,
                autoscale_volume=False,
            ),
        ],
    },
}


INDEX_FETCHER_CONFIGS = {
    "CexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "cex.json",
        "fetcher_class": CexFetcher,
        "name": "CEX",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(2601210000000 * 0.5 + 163921000000 * 0.5),
            12345,
            "CEX",
            PUBLISHER_NAME,
            autoscale_volume=False,
        ),
    },
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
            autoscale_volume=False,
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
            autoscale_volume=False,
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
            autoscale_volume=False,
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
            autoscale_volume=False,
        ),
    },
    "KaikoFetcher": {
        "mock_file": MOCK_DIR / "responses" / "kaiko.json",
        "fetcher_class": KaikoFetcher,
        "name": "Kaiko",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int((2601601000000 * 0.5) + 164315580431 * 0.5),
            12345,
            "KAIKO",
            PUBLISHER_NAME,
            autoscale_volume=False,
        ),
    },
    "TheGraphFetcher": {
        "mock_file": MOCK_DIR / "responses" / "thegraph.json",
        "fetcher_class": TheGraphFetcher,
        "name": "TheGraph",
        "expected_result": SpotEntry(
            "INDEXNAME1",
            int(3459885191309 * 0.5 + 0.5 * 180043642780),
            12345,
            "THEGRAPH",
            PUBLISHER_NAME,
            autoscale_volume=False,
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
            autoscale_volume=False,
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
}


ONCHAIN_STARKNET_FETCHER_CONFIGS = {
    "StarknetAMMFetcher": {
        "mock_file": MOCK_DIR / "responses" / "on_starknet_amm.json",
        "fetcher_class": StarknetAMMFetcher,
        "name": "ONStarknetAMM",
        "expected_result": [
            SpotEntry(
                "STRK/USD",
                (226416500000 / 10**8) / (71651396007433143 / 3381524279075682),
                12345,
                "STARKNET",
                PUBLISHER_NAME,
                volume=0,
            ),
            SpotEntry(
                "ETH/STRK",
                71651396007433143 / 3381524279075682,
                12345,
                "STARKNET",
                PUBLISHER_NAME,
                volume=0,
            ),
        ],
    },
}


INDEX_CONFIGS = {
    "IndexConfig": {
        "name": "IndexConfig",
        "expected_result": [
            SpotEntry(
                "INDEXNAME1",
                200000000000,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=0,
                autoscale_volume=False,
            ),
            SpotEntry(
                "INDEXNAME2",
                1500050000000000,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=0,
                autoscale_volume=False,
            ),
        ],
    },
}
