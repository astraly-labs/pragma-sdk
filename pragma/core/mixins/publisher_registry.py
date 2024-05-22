from typing import List

from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client

from pragma.core.contract import Contract
from pragma.core.utils import str_to_felt


class PublisherRegistryMixin:
    client: Client
    account: Account
    publisher_registry: Contract

    async def get_all_publishers(self) -> List[str]:
        (publishers,) = await self.publisher_registry.functions[
            "get_all_publishers"
        ].call()
        return publishers

    async def get_publisher_address(self, publisher) -> str:
        (address,) = await self.publisher_registry.functions[
            "get_publisher_address"
        ].call(publisher)
        return address

    async def get_publisher_sources(self, publisher) -> List[str]:
        (sources,) = await self.publisher_registry.functions[
            "get_publisher_sources"
        ].call(publisher)
        return sources

    async def add_publisher(
        self, publisher: str, publisher_address: int, max_fee=int(1e16)
    ) -> InvokeResult:
        invocation = await self.publisher_registry.functions["add_publisher"].invoke_v1(
            str_to_felt(publisher),
            publisher_address,
            max_fee=max_fee,
        )
        return invocation

    async def add_source_for_publisher(
        self, publisher: str, source: str, max_fee=int(1e16)
    ) -> InvokeResult:
        invocation = await self.publisher_registry.functions[
            "add_source_for_publisher"
        ].invoke_v1(
            str_to_felt(publisher),
            str_to_felt(source),
            max_fee=max_fee,
        )
        return invocation

    async def add_sources_for_publisher(
        self, publisher: str, sources: List[str], max_fee=int(1e16)
    ) -> InvokeResult:
        invocation = await self.publisher_registry.functions[
            "add_sources_for_publisher"
        ].invoke_v1(
            str_to_felt(publisher),
            [str_to_felt(source) for source in sources],
            max_fee=max_fee,
        )
        return invocation

    async def update_publisher_address(
        self, publisher: str, publisher_address: int, max_fee=int(1e16)
    ) -> InvokeResult:
        invocation = await self.publisher_registry.functions[
            "update_publisher_address"
        ].invoke_v1(
            str_to_felt(publisher),
            publisher_address,
            max_fee=max_fee,
        )
        return invocation
