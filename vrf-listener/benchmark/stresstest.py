import asyncio
from typing import List
from dataclasses import dataclass
from datetime import datetime

from pragma_sdk.onchain.types import (
    VRFRequestParams,
    RequestStatus,
)

from starknet_py.contract import Contract
from benchmark.pragma_client import ExtendedPragmaClient


@dataclass
class RequestInfo:
    hash: str
    request_time: datetime
    fulfillment_time: datetime = None


async def spam_requests(user: ExtendedPragmaClient, example_contract: Contract, num_requests: int):
    request_infos: List[RequestInfo] = []

    for _ in range(num_requests):
        invocation = await user.request_random(
            VRFRequestParams(
                seed=1,
                callback_address=example_contract.address,
                callback_fee_limit=2855600000000000000,
                publish_delay=1,
                num_words=1,
                calldata=[0x1234, 0x1434, 314141, 13401234],
            )
        )
        await invocation.wait_for_acceptance()
        request_hash = invocation.hash
        request_time = datetime.now()
        request_infos.append(RequestInfo(hash=request_hash, request_time=request_time))

    return request_infos


async def check_request_status(user: ExtendedPragmaClient, request_info: RequestInfo):
    while True:
        status = await user.get_request_status(user.account.address, request_info.hash)
        if status == RequestStatus.FULFILLED:
            request_info.fulfillment_time = datetime.now()
            break
        await asyncio.sleep(1)  # Check every second


async def process_user(user: ExtendedPragmaClient, example_contract: Contract, num_requests: int):
    request_infos = await spam_requests(user, example_contract, num_requests)
    await asyncio.gather(*[check_request_status(user, info) for info in request_infos])
    return request_infos
