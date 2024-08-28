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


async def submit_and_check_request(
    user: ExtendedPragmaClient, example_contract: Contract
) -> RequestInfo:
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
    request_info = RequestInfo(hash=invocation.hash, request_time=datetime.now())

    while True:
        status = await user.get_request_status(user.account.address, request_info.hash)
        if status == RequestStatus.FULFILLED:
            request_info.fulfillment_time = datetime.now()
            break
        await asyncio.sleep(0.5)  # Check every 0.5 secs

    return request_info


async def spam_reqs_with_user(
    user: ExtendedPragmaClient, example_contract: Contract, num_requests: int
) -> List[RequestInfo]:
    tasks = [submit_and_check_request(user, example_contract) for _ in range(num_requests)]
    return await asyncio.gather(*tasks)
