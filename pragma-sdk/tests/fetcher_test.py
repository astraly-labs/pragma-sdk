import asyncio
import argparse
import aiohttp
from datetime import datetime
from typing import Type, Optional, List

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.entry import SpotEntry, FutureEntry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.utils import felt_to_str

"""
Smol script to test any fetcher easily

e.g
```
python fetcher_test.py DefillamaFetcher BROTHER USDPLUS
```
"""


async def test_fetcher(
    fetcher_class: Type[FetcherInterfaceT],
    pairs: List[Pair],
    api_key: Optional[str] = None,
    is_future: bool = False,
) -> None:
    """
    Test a price fetcher for multiple currency pairs.

    Args:
        fetcher_class: The fetcher class to test
        pairs: List of currency pairs to fetch
        api_key: Optional API key for the fetcher
        is_future: Whether the fetcher is a future fetcher
    """
    fetcher = fetcher_class(pairs=pairs, publisher="TEST")

    if api_key and hasattr(fetcher, "headers"):
        fetcher.headers["Authorization"] = f"Bearer {api_key}"

    print(
        f"\nTesting {fetcher.__class__.__name__} for pairs: {[str(pair) for pair in pairs]}"
    )
    print("-" * 50)

    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            results = await fetcher.fetch(session)
            end_time = datetime.now()
            fetch_time = (end_time - start_time).total_seconds()

            print(f"Fetch completed in {fetch_time:.3f}s")
            print(f"Number of results: {len(results)}")

            for idx, result in enumerate(results):
                print(f"\nResult {idx + 1}:")
                if isinstance(result, (SpotEntry, FutureEntry)):
                    pair = pairs[idx]
                    print("✅ Successfully fetched price:")
                    print(f"  Pair: {pair}")
                    print(f"  Price: {result.price}")
                    print(
                        f"  Human readable price: {result.price / (10 ** pair.decimals())}"
                    )
                    print(f"  Timestamp: {result.base.timestamp}")
                    print(
                        f"  Human readable time: {datetime.fromtimestamp(result.base.timestamp)}"
                    )
                    print(f"  Volume: {result.volume}")
                    print(f"  Source: {felt_to_str(result.base.source)}")
                    print(f"  Publisher: {felt_to_str(result.base.publisher)}")
                    if isinstance(result, FutureEntry):
                        print(
                            f"  Expiry: {datetime.fromtimestamp(result.expiry_timestamp)}"
                        )
                elif isinstance(result, PublisherFetchError):
                    print("❌ Error fetching price:")
                    print(f"  Error message: {str(result)}")
                else:
                    print("❌ Unexpected result type:")
                    print(f"  {type(result)}: {result}")

    except Exception as e:
        print("❌ Exception occurred:")
        print(f"  {type(e).__name__}: {str(e)}")


def parse_pair(pair_str: str) -> Pair:
    """Parse a pair string in format 'BTC/USD' into a Pair object."""
    try:
        base, quote = pair_str.split("/")
        base_currency = Currency.from_asset_config(AssetConfig.from_ticker(base))
        quote_currency = Currency.from_asset_config(AssetConfig.from_ticker(quote))
        return Pair(base_currency, quote_currency)
    except ValueError:
        raise ValueError(
            f"Invalid pair format: {pair_str}. Expected format: BASE/QUOTE (e.g., BTC/USD)"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Test a price fetcher for multiple currency pairs"
    )
    parser.add_argument(
        "fetcher", type=str, help="Fetcher class name (e.g., BinanceFutureFetcher)"
    )
    parser.add_argument(
        "pairs",
        type=str,
        nargs="+",
        help="Currency pairs in format BASE/QUOTE (e.g., BTC/USD ETH/USD)",
    )
    parser.add_argument(
        "--api-key", type=str, help="API key for the fetcher", default=None
    )
    parser.add_argument(
        "--future", action="store_true", help="Use future fetcher module path"
    )

    args = parser.parse_args()

    try:
        # Parse all pairs
        pairs = [parse_pair(pair_str) for pair_str in args.pairs]

        # Handle the module name conversion
        module_name = args.fetcher.lower()

        # For future fetchers, we want 'binance' from 'BinanceFutureFetcher'
        if args.future:
            if module_name.endswith("futurefetcher"):
                module_name = module_name.replace("futurefetcher", "")
        else:
            if module_name.endswith("fetcher"):
                module_name = module_name.replace("fetcher", "")

        # Construct the correct import path
        if args.future:
            import_path = f"pragma_sdk.common.fetchers.future_fetchers.{module_name}"
        else:
            import_path = f"pragma_sdk.common.fetchers.fetchers.{module_name}"

        print(f"Attempting to import from: {import_path}")
        fetcher_module = __import__(
            import_path,
            fromlist=[args.fetcher],
        )
        fetcher_class = getattr(fetcher_module, args.fetcher)

        asyncio.run(
            test_fetcher(
                fetcher_class=fetcher_class,
                pairs=pairs,
                api_key=args.api_key,
                is_future=args.future,
            )
        )

    except ImportError as e:
        print(f"❌ Could not import fetcher class '{args.fetcher}' from {import_path}")
        print(f"  Error: {str(e)}")
    except AttributeError as e:
        print(f"❌ Could not find fetcher class '{args.fetcher}' in module")
        print(f"  Error: {str(e)}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    main()
