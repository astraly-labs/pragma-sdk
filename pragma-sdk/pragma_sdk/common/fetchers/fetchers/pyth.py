import asyncio
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

# Mapping of currency pairs to Pyth feed IDs
PYTH_FEED_IDS: Dict[str, str] = {
    # Major cryptocurrencies
    "BTC/USD": "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "USDT/USD": "0x2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b",
    "ETH/USD": "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "SOL/USD": "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "BNB/USD": "0x2f95862b045670cd22bee3114c39763a4a08beeb663b145d283c31d7d1101c4f",
    "XRP/USD": "0xec5d399846a9209f3fe5881d70aae9268c94339ff9817e8d18ff19fa05eea1c8",
    "ADA/USD": "0x2a01deaec9e51a579277b34b122399984d0bbf57e2458a7e42fecd2829867a0d",
    "AVAX/USD": "0x93da3352f9f1d105fdfe4971cfa80e9dd777bfc5d0f683ebb6e1294b92137bb7",
    "MATIC/USD": "0xffd11c5a1cfd42f80afb2df4d9f264c15f956d68153335374ec10722edd70472",
    "DOGE/USD": "0xdcef50dd0a4cd2dcc17e45df1676dcb336a11a61c69df7a0299b0150c672d25c",
    "TRX/USD": "0x67aed5a24fdad045475e7195c98a98aea119c763f272d4523f5bac93a4f33c2b",
    "LINK/USD": "0x8ac0c70fff57e9aefdf5edf44b51d62c2d433653cbb2cf5cc06bb115af04d221",
    "DOT/USD": "0xca3eed9b267293f6595901c734c7525ce8ef49adafe8284606ceb307afa2ca5b",
    "LTC/USD": "0x6e3f3fa8253588df9326580180233eb791e03b443a3ba7a1d892e73874e19a54",
    "BCH/USD": "0x3dd2b63686a450ec7290df3a1e0b583c0481f651351edfa7636f39aed55cf8a3",
    "ATOM/USD": "0xb00b60f88b03a6a625a8d1c048c3f66653edf217439983d037e7222c4e612819",
    "UNI/USD": "0x78d185a741d07edb3412b09008b7c5cfb9bbbd7d568bf00ba737b456ba171501",
    "FIL/USD": "0x150ac9b959aee0051e4091f0ef5216d941f590e1c5e7f91cf7635b5c11628c0e",
    "NEAR/USD": "0xc415de8d2eba7db216527dff4b60e8f3a5311c740dadb233e13e12547e226750",
    "APT/USD": "0x03ae4db29ed4ae33d323568895aa00337e658e348b37509f5372ae51f0af00d5",
    "ARB/USD": "0x3fa4252848f9f0a1480be62745a4629d9eb1322aebab8a791e344b3b9c1adcf5",
    "OP/USD": "0x385f64d993f7b77d8182ed5003d97c60aa3361f3cecfe711544d2d59165e9bdf",
    "SUI/USD": "0x23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744",
    "SEI/USD": "0x53614f1cb0c031d4af66c04cb9c756234adad0e1cee85303795091499a4084eb",
    "INJ/USD": "0x7a5bc1d2b56ad029048cd63964b3ad2776eadf812edc1a43a31406cb54bff592",
    "JTO/USD": "0x0a31cdb154c042b5a8d1329044acb02b7c0f0e4a96ef62cf4d3c2c8178c873d0",
    "JUP/USD": "0x0a0408d619e9380abad35060f9192039ed5042fa6f82301d0e48bb52be830996",
    "TIA/USD": "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723",
    "WLD/USD": "0xd6835ad1f773de4a378115eb6824bd0c0e42d84d1c84d9750e853fb6b6c7794a",
    "BONK/USD": "0x72b021217ca3fe68922a19aaf990109cb9d84e9ad004b4d2025ad6f529314419",
    "FTM/USD": "0xb2748e718cf3a75b0ca099cb467aea6aa8f7d960b381b3970769b5a2d6be26dc",
    "SHIB/USD": "0xf0d57deca57b3da2fe63a493f4c25925fdfd8edf834b20f93e1f84dbd1504d4a",
    "CRV/USD": "0xa19d04ac696c7a6616d291c7e5d1377cc8be437c327b75adb5dc1bad745fcae8",
    "LDO/USD": "0xc63e2a7f37a04e5e614c07238bedb25dcc38927fba8fe890597a593c0b2fa4ad",
    "AAVE/USD": "0x2b9ab1e972a281585084148ba1389800799bd4be63b957507db1349314e47445",
    "APE/USD": "0x15add95022ae13563a11992e727c91bdb6b55bc183d9d747436c80a483d8c864",
    "TON/USD": "0x8963217838ab4cf5cadc172203c1f0b763fbaa45f346d8ee50ba994bbcac3026",
    "XEC/USD": "0x44622616f246ce5fc46cf9ebdb879b0c0157275510744cea824ad206e48390b3",
    "STRK/USD": "0x6a182399ff70ccf3e06024898942028204125a819e519a335ffa4579e66cd870",
    "WSTETH/USD": "0x6df640f3b8963d8f8358f791f352b8364513f6ab1cca5ed3f1f7b5448980e784",
    "EUR/USD": "0xa995d00bb36a63cef7fd2c287dc105fc8f3d93779f062f09551b0af3e81ec30b",
}


class PythFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://hermes.pyth.network/v2/updates/price/latest"
    SOURCE: str = "PYTH"

    def get_feed_id(self, pair: Pair) -> Optional[str]:
        """Get the Pyth feed ID for a given currency pair."""
        pair_str = f"{pair.base_currency.id}/{pair.quote_currency.id}"
        return PYTH_FEED_IDS.get(pair_str)

    def format_url(self, feed_ids: List[str]) -> str:
        """Format URL with feed IDs for batch request."""
        params = "&".join([f"ids[]={feed_id}" for feed_id in feed_ids])
        return f"{self.BASE_URL}?{params}"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, feed_id: Optional[str] = None
    ) -> SpotEntry | PublisherFetchError:
        """Fetch price for a single pair."""
        if not feed_id:
            return PublisherFetchError(f"No Pyth feed ID found for pair {pair}")

        url = self.format_url([feed_id])

        async with session.get(url) as resp:
            if resp.status != 200:
                return PublisherFetchError(f"Failed to fetch data for {pair} from Pyth")

            result = await resp.json()
            if not result or "parsed" not in result or not result["parsed"]:
                return PublisherFetchError(f"No data found for {pair} from Pyth")

            # Find the matching price feed from parsed results
            price_feed = next(
                (
                    feed
                    for feed in result["parsed"]
                    if feed["id"].replace("0x", "") == feed_id.replace("0x", "")
                ),
                None,
            )
            if not price_feed:
                return PublisherFetchError(
                    f"No matching price feed found for {pair} from Pyth"
                )

            return self._construct(pair, price_feed)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """Fetch prices for all pairs."""
        entries = []
        for pair in self.pairs:
            feed_id = self.get_feed_id(pair)
            entries.append(
                asyncio.ensure_future(self.fetch_pair(pair, session, feed_id))
            )

        return list(await asyncio.gather(*entries, return_exceptions=True))

    def _construct(self, pair: Pair, result: Any) -> SpotEntry:
        """Construct a SpotEntry from the Pyth price data."""
        price_data = result["price"]
        price = int(price_data["price"]) / (10 ** abs(price_data["expo"]))
        conf = int(price_data["conf"]) / (10 ** abs(price_data["expo"]))
        timestamp = int(price_data["publish_time"])
        price_int = int(price * (10 ** pair.decimals()))

        logger.debug("Fetched price %d (±%f) for %s from Pyth", price_int, conf, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
