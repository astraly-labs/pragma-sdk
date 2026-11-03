"""
Validator publishers are identified by their staker address, not a short string.
"""

import pytest

from pragma_sdk.common.types.entry import FutureEntry, GenericEntry, SpotEntry
from pragma_sdk.common.utils import publisher_to_felt, publisher_to_str, str_to_felt

STAKER = "0x077d4b4e7ae321aabd0a5a7322108635fcbd0cd746f9ae217b8ea00363494b65"


def test_short_string_publisher_is_unchanged():
    assert publisher_to_felt("PRAGMA") == str_to_felt("PRAGMA")
    assert publisher_to_felt("pragma") == str_to_felt("PRAGMA")


@pytest.mark.parametrize("publisher", [STAKER, STAKER.upper().replace("0X", "0x")])
def test_hex_publisher_is_an_address(publisher):
    assert publisher_to_felt(publisher) == int(STAKER, 16)


def test_int_publisher_is_kept():
    assert publisher_to_felt(42) == 42


def test_publisher_to_str():
    assert publisher_to_str(str_to_felt("PRAGMA")) == "PRAGMA"
    assert publisher_to_str(int(STAKER, 16)) == hex(int(STAKER, 16))


def test_entries_accept_an_address_publisher():
    spot = SpotEntry("BTC/USD", 1, 1, "BINANCE", STAKER)
    future = FutureEntry("BTC/USD", 1, 1, "BINANCE", STAKER, 0)
    generic = GenericEntry("KEY", 1, 1, "BINANCE", STAKER)
    for entry in (spot, future, generic):
        assert entry.base.publisher == int(STAKER, 16)
        assert hex(int(STAKER, 16)) in repr(entry)
