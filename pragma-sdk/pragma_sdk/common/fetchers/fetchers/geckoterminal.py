import time
from typing import Any, Dict, List

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


ASSET_MAPPING: Dict[str, Any] = {
    "LORDS": (
        "starknet-alpha",
        "0x124aeb495b947201f5fac96fd1138e326ad86195b98df6dec9009158a533b49",
    ),
    "R": ("eth", "0x183015a9ba6ff60230fdeadc3f43b3d788b13e21"),
    "WBTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "BTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "WSTETH": ("eth", "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"),
    "ETH": ("eth", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
    "UNI": ("eth", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"),
    "LUSD": ("eth", "0x5f98805a4e8be255a32880fdec7f6728c6568ba0"),
    "STRK": (
        "starknet-alpha",
        "0x4718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d",
    ),
    "XSTRK": (
        "starknet-alpha",
        "0x028d709c875C0CEAc3dCE7065beC5328186Dc89FE254527084D1689910954B0a",
    ),
    "SSTRK": (
        "starknet-alpha",
        "0x0356f304b154d29d2a8fe22f1cb9107a9b564a733cf6b4cc47fd121ac1af90c9",
    ),
    "KSTRK": (
        "starknet-alpha",
        "0x045cd05ee2caaac3459b87e5e2480099d201be2f62243f839f00e10dde7f500c",
    ),
    "ZEND": (
        "starknet-alpha",
        "0x00585c32b625999e6e5e78645ff8df7a9001cf5cf3eb6b80ccdd16cb64bd3a34",
    ),
    "YFI": (
        "eth",
        "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e",
    ),
    "EKUBO": (
        "starknet-alpha",
        "0x75afe6402ad5a5c20dd25e10ec3b3986acaa647b77e4ae24b0cbc9a54a27a87",
    ),
    "COMP": ("eth", "0xc00e94Cb662C3520282E6f5717214004A7f26888"),
    "SNX": ("eth", "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F"),
    "MKR": ("eth", "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"),
    "BAL": ("eth", "0xba100000625a3754423978a60c9317c58a424e3D"),
    "AAVE": ("eth", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
    "LDO": ("eth", "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32"),
    "RPL": ("eth", "0xD33526068D116cE69F19A9ee46F0bd304F21A51f"),
    "WETH": ("eth", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "MC": ("eth", "0x949d48eca67b17269629c7194f4b727d4ef9e5d6"),
    "RNDR": ("eth", "0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24"),
    "FET": ("eth", "0xaea46A60368A7bD060eec7DF8CBa43b7EF41Ad85"),
    "IMX": ("eth", "0xf57e7e7c23978c3caec3c3548e3d615c346e79ff"),
    "GALA": ("eth", "0xd1d2Eb1B1e90B638588728b4130137D262C87cae"),
    "ILV": ("eth", "0x767fe9edc9e0df98e07454847909b5e959d7ca0e"),
    "SAND": ("eth", "0x3845badAde8e6dFF049820680d1F14bD3903a5d0"),
    "AXS": ("eth", "0xbb0e17ef65f82ab018d8edd776e8dd940327b28b"),
    "MANA": ("eth", "0x0f5d2fb29fb7d3cfee444a200298f468908cc942"),
    "ENS": ("eth", "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72"),
    "BLUR": ("eth", "0x5283d291dbcf85356a21ba090e6db59121208b44"),
    "DPI": ("eth", "0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b"),
    "MVI": ("eth", "0x72e364f2abdc788b7e918bc238b21f109cd634d7"),
    # Nostra's token lives on Starknet; the eth address was an unrelated "NSTR".
    "NSTR": (
        "starknet-alpha",
        "0x00c530f2c0aa4c16a0806365b0898499fba372e5df7a7172dc6fe9ba777e8007",
    ),
    "BROTHER": (
        "starknet-alpha",
        "0x3b405a98c9e795d427fe82cdeeeed803f221b52471e3a757574a2b4180793ee",
    ),
    "SURVIVOR": (
        "starknet-alpha",
        "0x042dd777885ad2c116be96d4d634abc90a26a790ffb5871e037dd5ae7d2ec86b",
    ),
}


def _normalize(address: str) -> str:
    """GeckoTerminal pads Starknet addresses (0x0124…) where our mapping does not."""
    try:
        return hex(int(address, 16))
    except (TypeError, ValueError):
        return address.lower()


class GeckoTerminalFetcher(FetcherInterfaceT):
    """
    One request per network for every configured token (the public API
    rate-limits after three calls in a burst, and a 429 payload has no data).
    A token is only a price when GeckoTerminal sees real liquidity behind it
    (MIN_RESERVE_USD across its pools) and still trades at all (non-zero 24h
    volume). The volume check is a dead-market check, nothing more: the API
    aggregates volume over every pool while the price comes from the main one,
    and 24h is slow. Freshness beyond that is the cross-source guard's job.
    """

    BASE_URL: str = "https://api.geckoterminal.com/api/v2/networks/{network}/tokens/multi/{addresses}"
    SOURCE: str = "GECKOTERMINAL"
    MIN_RESERVE_USD: float = 20_000

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        results = await self.fetch_pairs([pair], session)
        return results[0]  # type: ignore[return-value]

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        return await self.fetch_pairs(self.pairs, session)

    def format_url(self, pair: Pair) -> str:
        pool = ASSET_MAPPING[pair.base_currency.id]
        return self.BASE_URL.format(network=pool[0], addresses=pool[1])

    async def fetch_pairs(
        self, pairs: List[Pair], session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        # tokens needed per network: the base, and the quote when it is not USD
        needed: Dict[str, Dict[str, str]] = {}
        unknown: Dict[int, PublisherFetchError] = {}
        for idx, pair in enumerate(pairs):
            for currency in self._tokens_for(pair):
                pool = ASSET_MAPPING.get(currency)
                if pool is None:
                    unknown[idx] = PublisherFetchError(
                        f"Unknown price pair, do not know how to query GeckoTerminal "
                        f"for {pair.base_currency} to {pair.quote_currency}"
                    )
                    break
                needed.setdefault(pool[0], {})[_normalize(pool[1])] = currency

        quotes: Dict[str, Dict[str, Any] | PublisherFetchError] = {}
        for network, addresses in needed.items():
            quotes.update(await self._fetch_network(network, list(addresses), session))

        entries: List[Entry | PublisherFetchError | BaseException] = []
        for idx, pair in enumerate(pairs):
            if idx in unknown:
                entries.append(unknown[idx])
                continue
            entries.append(self._construct(pair, quotes))
        return entries

    @staticmethod
    def _tokens_for(pair: Pair) -> List[str]:
        tokens = [pair.base_currency.id]
        if pair.quote_currency.id not in ("USD", "USDPLUS"):
            tokens.append(pair.quote_currency.id)
        return tokens

    async def _fetch_network(
        self, network: str, addresses: List[str], session: ClientSession
    ) -> Dict[str, Dict[str, Any] | PublisherFetchError]:
        """Price attributes per lowercase address, or one error for all of them."""
        url = self.BASE_URL.format(network=network, addresses=",".join(addresses))
        async with session.get(url, headers=self.headers) as resp:
            try:
                result = await resp.json()
            except Exception:  # noqa: BLE001
                result = None
            if (
                resp.status != 200
                or not isinstance(result, dict)
                or "data" not in result
            ):
                detail = (
                    (result.get("status") or {}).get("error_message")
                    if isinstance(result, dict)
                    else None
                )
                error = PublisherFetchError(
                    f"GeckoTerminal {network}: HTTP {resp.status}"
                    + (f", {detail}" if detail else "")
                )
                return {address: error for address in addresses}
        found: Dict[str, Dict[str, Any] | PublisherFetchError] = {}
        for token in result.get("data") or []:
            attributes = token.get("attributes") or {}
            address = _normalize(str(attributes.get("address", "")))
            if address:
                found[address] = attributes
        for address in addresses:
            found.setdefault(
                address,
                PublisherFetchError(f"No data found for {address} from GeckoTerminal"),
            )
        return found

    def _usd_price(
        self, currency: str, quotes: Dict[str, Dict[str, Any] | PublisherFetchError]
    ) -> float | PublisherFetchError:
        pool = ASSET_MAPPING[currency]
        attributes = quotes.get(_normalize(pool[1]))
        if attributes is None:
            return PublisherFetchError(
                f"No data found for {currency} from GeckoTerminal"
            )
        if isinstance(attributes, PublisherFetchError):
            return attributes
        try:
            price = float(attributes["price_usd"])
            reserve = float(attributes.get("total_reserve_in_usd") or 0)
            volume = float((attributes.get("volume_usd") or {}).get("h24") or 0)
        except (TypeError, ValueError, KeyError):
            return PublisherFetchError(
                f"No data found for {currency} from GeckoTerminal"
            )
        if price <= 0:
            return PublisherFetchError(f"No price for {currency} from GeckoTerminal")
        if reserve < self.MIN_RESERVE_USD or volume <= 0:
            return PublisherFetchError(
                f"{currency} on GeckoTerminal is too thin to be a price: "
                f"reserve ${reserve:,.0f} (min ${self.MIN_RESERVE_USD:,.0f}), "
                f"24h volume ${volume:,.0f}"
            )
        return price

    def _construct(
        self, pair: Pair, quotes: Dict[str, Dict[str, Any] | PublisherFetchError]
    ) -> SpotEntry | PublisherFetchError:
        base = self._usd_price(pair.base_currency.id, quotes)
        if isinstance(base, PublisherFetchError):
            return base
        price = base
        if pair.quote_currency.id not in ("USD", "USDPLUS"):
            quote = self._usd_price(pair.quote_currency.id, quotes)
            if isinstance(quote, PublisherFetchError):
                return quote
            price = base / quote

        attributes = quotes[_normalize(ASSET_MAPPING[pair.base_currency.id][1])]
        volume = float((attributes.get("volume_usd") or {}).get("h24") or 0)  # type: ignore[union-attr]
        price_int = int(price * (10 ** pair.decimals()))
        logger.debug("Fetched price %d for %s from GeckoTerminal", price_int, pair)
        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=int(volume),
        )
