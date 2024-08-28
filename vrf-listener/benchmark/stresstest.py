import asyncio
from typing import List
from dataclasses import dataclass
from datetime import datetime

from pragma_sdk.onchain.types import (
    VRFRequestParams,
    RequestStatus,
)

from starknet_py.contract import Contract, TypeSentTransaction
from benchmark.pragma_client import ExtendedPragmaClient

# Time to wait between request status check (in secs)
TTW_BETWEEN_REQ_CHECK = 0.1


@dataclass
class RequestInfo:
    hash: str
    sent_tx: TypeSentTransaction
    request_time: datetime
    fulfillment_time: datetime = None


async def create_request(user: ExtendedPragmaClient, example_contract: Contract) -> RequestInfo:
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
    return RequestInfo(
        hash=invocation.hash,
        sent_tx=invocation,
        request_time=datetime.now(),
    )


async def check_request_status(user: ExtendedPragmaClient, request_info: RequestInfo):
    while True:
        await request_info.sent_tx.wait_for_acceptance()
        status = await user.get_request_status(user.account.address, request_info.hash)
        if status == RequestStatus.FULFILLED:
            request_info.fulfillment_time = datetime.now()
            break
        await asyncio.sleep(TTW_BETWEEN_REQ_CHECK)


async def spam_reqs_with_user(
    user: ExtendedPragmaClient, example_contract: Contract, num_requests: int = 10
) -> List[RequestInfo]:
    request_infos = []
    status_check_tasks = []

    async def create_and_check():
        request_info = await create_request(user, example_contract)
        request_infos.append(request_info)
        status_check_tasks.append(asyncio.create_task(check_request_status(user, request_info)))

    # Create requests and start checking their status concurrently
    await asyncio.gather(*[create_and_check() for _ in range(num_requests)])

    # Wait for all status checks to complete
    await asyncio.gather(*status_check_tasks)

    return request_infos
