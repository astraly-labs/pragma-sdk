import click

from typing import List, Set

from pragma_sdk.common.types.types import Address


def validate_hex_string(value: str) -> str:
    if not value.startswith("0x") or not all(c in "0123456789ABCDEFabcdef" for c in value[2:]):
        raise ValueError(f"Invalid hexadecimal string: {value}")
    return value


class HexStringCliArg(click.ParamType):
    name = "hex_string"

    def convert(self, value, param, ctx):
        try:
            return validate_hex_string(value)
        except ValueError:
            self.fail(f"{value!r} is not a valid hexadecimal string", param, ctx)


HEX_STRING = HexStringCliArg()


def hex_addresses_list_to_addresses_set(addresses: List[str]) -> Set[Address]:
    return set([int(addr, 16) for addr in addresses])
