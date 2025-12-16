# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pragma-sdk",
#     "matplotlib",
# ]
# ///
"""
Script to plot CONVERSION_XSTRK/USD, STRK/USD, and CONVERSION_XSTRK/STRK feed data
over the last 6 hours (21600 blocks).
"""

import asyncio
from datetime import datetime

import matplotlib.pyplot as plt
from pragma_sdk.common.types.types import AggregationMode
from pragma_sdk.onchain.client import PragmaOnChainClient

PAIRS = [
    "CONVERSION_XSTRK/USD",
    "STRK/USD",
]


async def fetch_pair_data(client, pair_id: str, blocks: list[int]) -> dict:
    """Fetch price data for a single pair across multiple blocks."""
    prices = []
    timestamps = []
    valid_blocks = []

    print(f"\nFetching {pair_id}...")

    for i, block in enumerate(blocks):
        try:
            response = await client.get_spot(
                pair_id=pair_id,
                aggregation_mode=AggregationMode.MEDIAN,
                block_id=block,
            )
            price = response.price / (10**response.decimals)
            prices.append(price)
            timestamps.append(response.last_updated_timestamp)
            valid_blocks.append(block)

            if (i + 1) % 20 == 0:
                print(f"  {pair_id}: {i + 1}/{len(blocks)} data points...")

        except Exception as e:
            print(f"  Error fetching {pair_id} at block {block}: {e}")
            continue

    return {
        "pair_id": pair_id,
        "blocks": valid_blocks,
        "prices": prices,
        "timestamps": timestamps,
    }


async def fetch_all_data():
    client = PragmaOnChainClient(network="mainnet")

    current_block = await client.get_block_number()
    print(f"Current block: {current_block}")

    # Fetch data for the last 20000 blocks (~5.5 hours with 1 sec block time)
    num_blocks = 20000
    start_block = current_block - num_blocks

    # Sample every 100 blocks (~1.6 min intervals) = 200 data points
    step = 100
    blocks = list(range(start_block, current_block + 1, step))

    print(f"Fetching data from block {start_block} to {current_block}")
    print(f"Data points per pair: {len(blocks)}")

    results = {}
    for pair_id in PAIRS:
        data = await fetch_pair_data(client, pair_id, blocks)
        results[pair_id] = data

    # Compute CONVERSION_XSTRK/STRK by dividing CONVERSION_XSTRK/USD by STRK/USD
    xstrk_usd = results["CONVERSION_XSTRK/USD"]
    strk_usd = results["STRK/USD"]

    ratio_prices = []
    ratio_timestamps = []
    ratio_blocks = []

    for i, block in enumerate(xstrk_usd["blocks"]):
        if block in strk_usd["blocks"]:
            j = strk_usd["blocks"].index(block)
            if strk_usd["prices"][j] > 0:
                ratio = xstrk_usd["prices"][i] / strk_usd["prices"][j]
                ratio_prices.append(ratio)
                ratio_timestamps.append(xstrk_usd["timestamps"][i])
                ratio_blocks.append(block)

    results["CONVERSION_XSTRK/STRK"] = {
        "pair_id": "CONVERSION_XSTRK/STRK",
        "blocks": ratio_blocks,
        "prices": ratio_prices,
        "timestamps": ratio_timestamps,
    }

    return results


def plot_data(results: dict):
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    colors = {
        "CONVERSION_XSTRK/USD": "blue",
        "STRK/USD": "green",
        "CONVERSION_XSTRK/STRK": "purple",
    }

    all_pairs = PAIRS + ["CONVERSION_XSTRK/STRK"]

    for ax, pair_id in zip(axes, all_pairs):
        data = results[pair_id]
        if not data["prices"]:
            continue

        datetimes = [datetime.fromtimestamp(ts) for ts in data["timestamps"]]
        color = colors[pair_id]

        ax.plot(
            datetimes,
            data["prices"],
            "-",
            linewidth=1.5,
            marker="o",
            markersize=3,
            color=color,
        )
        ax.set_ylabel("Price")
        ax.set_title(pair_id)
        ax.grid(True, alpha=0.3)

        if data["prices"]:
            ax.legend(
                [f"Range: {min(data['prices']):.6f} - {max(data['prices']):.6f}"],
                loc="upper right",
            )

    axes[-1].set_xlabel("Time")
    plt.xticks(rotation=45)
    plt.tight_layout()

    output_path = "xstrk_feeds.png"
    plt.savefig(output_path, dpi=150)
    print(f"\nPlot saved to {output_path}")

    plt.show()


async def main():
    results = await fetch_all_data()

    for pair_id, data in results.items():
        if data["prices"]:
            print(
                f"\n{pair_id}: {len(data['prices'])} points, range: {min(data['prices']):.6f} - {max(data['prices']):.6f}"
            )

    plot_data(results)


if __name__ == "__main__":
    asyncio.run(main())
