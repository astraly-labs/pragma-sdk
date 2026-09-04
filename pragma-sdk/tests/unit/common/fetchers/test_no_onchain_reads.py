"""
Architecture guard: a fetcher must never derive an entry from a value read in
Pragma's own oracle. On 2026-09-04 a thin USDT/USD median (2.04) was multiplied
into every USDT-quoted CEX entry and every ETH/BTC-quoted on-chain feed.
References come from `handlers/reference_price.py` only.

Any new on-chain read under `pragma_sdk/common/fetchers` fails this test unless
it is explicitly allow-listed here with a justification.
"""

import re
from pathlib import Path

FETCHERS_DIR = Path(__file__).parents[4] / "pragma_sdk" / "common" / "fetchers"

ONCHAIN_READ = re.compile(
    r"\.get_(spot|future|data|data_median|data_median_for_sources|entry)(_sync)?\("
)

# path (relative to fetchers/) -> why an on-chain read is tolerated there
ALLOWED = {
    # LP underlyings are Starknet-native tokens with no CEX reference. The read
    # is guarded (>= 3 sources, < 1h old), see _get_token_price_and_decimals.
    "generic_fetchers/lp_fetcher/fetcher.py": "guarded on-chain underlying price",
}


def test_fetchers_never_read_pragma_oracle_prices():
    offenders = {}
    for path in FETCHERS_DIR.rglob("*.py"):
        rel = path.relative_to(FETCHERS_DIR).as_posix()
        if rel in ALLOWED:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ONCHAIN_READ.search(line):
                offenders.setdefault(rel, []).append(f"{lineno}: {stripped}")
    assert not offenders, (
        "Fetchers must not read prices from Pragma's oracle (feedback loop). "
        f"Use handlers/reference_price.py instead. Offenders: {offenders}"
    )


def test_allowlist_is_still_accurate():
    for rel in ALLOWED:
        text = (FETCHERS_DIR / rel).read_text()
        assert ONCHAIN_READ.search(
            text
        ), f"{rel} no longer reads the oracle, remove it from ALLOWED"
