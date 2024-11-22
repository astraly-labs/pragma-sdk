import asyncio
import argparse
import aiohttp
from datetime import datetime
from typing import Type, Optional

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.entry import SpotEntry
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
    base_currency: str,
    quote_currency: str,
    api_key: Optional[str] = None,
) -> None:
    """
    Test a price fetcher for a specific currency pair.

    Args:
        fetcher_class: The fetcher class to test
        base_currency: Base currency ticker (e.g., "BTC")
        quote_currency: Quote currency ticker (e.g., "USD")
        api_key: Optional API key for the fetcher
    """
    # Create the currency pair
    base = Currency.from_asset_config(AssetConfig.from_ticker(base_currency))
    quote = Currency.from_asset_config(AssetConfig.from_ticker(quote_currency))
    pair = Pair(base, quote)

    # Initialize the fetcher
    fetcher = fetcher_class(pairs=[pair], publisher="TEST")

    # Set API key if provided
    if api_key and hasattr(fetcher, "headers"):
        fetcher.headers["Authorization"] = f"Bearer {api_key}"

    print(f"\nTesting {fetcher.__class__.__name__} for pair: {pair}")
    print("-" * 50)

    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            results = await fetcher.fetch(session)
            result = results[0]
            end_time = datetime.now()

            if isinstance(result, SpotEntry):
                print("✅ Successfully fetched price:")
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
                print(f"  Fetch time: {(end_time - start_time).total_seconds():.3f}s")
            elif isinstance(result, PublisherFetchError):
                print("❌ Error fetching price:")
                print(f"  Error message: {str(result)}")
            else:
                print("❌ Unexpected result type:")
                print(f"  {type(result)}: {result}")

    except Exception as e:
        print("❌ Exception occurred:")
        print(f"  {type(e).__name__}: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Test a price fetcher for a specific currency pair"
    )
    parser.add_argument(
        "fetcher", type=str, help="Fetcher class name (e.g., GeckoTerminalFetcher)"
    )
    parser.add_argument("base", type=str, help="Base currency ticker (e.g., BTC)")
    parser.add_argument("quote", type=str, help="Quote currency ticker (e.g., USD)")
    parser.add_argument(
        "--api-key", type=str, help="API key for the fetcher", default=None
    )

    args = parser.parse_args()

    # Import the fetcher class dynamically
    try:
        # This assumes the fetcher is in the same directory
        # You might need to modify this to import from different locations
        module_name = args.fetcher.lower()
        if module_name.endswith("fetcher"):
            module_name = module_name[:-7]

        fetcher_module = __import__(
            f"pragma_sdk.common.fetchers.fetchers.{module_name}",
            fromlist=[args.fetcher],
        )
        fetcher_class = getattr(fetcher_module, args.fetcher)

        asyncio.run(
            test_fetcher(
                fetcher_class=fetcher_class,
                base_currency=args.base,
                quote_currency=args.quote,
                api_key=args.api_key,
            )
        )

    except ImportError as e:
        print(f"❌ Could not import fetcher class '{args.fetcher}', {e}")
    except AttributeError:
        print(f"❌ Could not find fetcher class '{args.fetcher}' in module")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    main()
