import asyncio
from typing import List
from dataclasses import dataclass
from datetime import datetime
from asyncio import Queue

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
    tx_hash: str
    sent_tx: TypeSentTransaction
    request_time: datetime
    fulfillment_time: datetime = None
    request_id: int = None


async def get_request_id(user: ExtendedPragmaClient, req: RequestInfo) -> int:
    receipt = await user.full_node_client.get_transaction_receipt(tx_hash=req.tx_hash)
    request_id = receipt.events[2].data[0]
    return request_id


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
        tx_hash=invocation.hash,
        sent_tx=invocation,
        request_time=datetime.now(),
    )


async def check_request_status(user: ExtendedPragmaClient, request_info: RequestInfo):
    request_info.request_id = await get_request_id(user, request_info)
    await request_info.sent_tx.wait_for_acceptance()
    while True:
        status = await user.get_request_status(user.account.address, request_info.request_id)
        if status == RequestStatus.FULFILLED:
            request_info.fulfillment_time = datetime.now()
            break
        await asyncio.sleep(TTW_BETWEEN_REQ_CHECK)


async def request_creator(
    user: ExtendedPragmaClient,
    user_no: int,
    example_contract: Contract,
    num_requests: int,
    queue: Queue,
):
    for _ in range(num_requests):
        print(f"User {user_no} creating request...")
        request_info = await create_request(user, example_contract)
        await queue.put(request_info)
    await queue.put(None)  # Signal that we're done creating requests


async def status_checker(user: ExtendedPragmaClient, queue: Queue, results: List[RequestInfo]):
    while True:
        request_info = await queue.get()
        if request_info is None:
            break
        await check_request_status(user, request_info)
        results.append(request_info)


async def spam_reqs_with_user(
    user: ExtendedPragmaClient, user_no: int, example_contract: Contract, num_requests: int = 10
) -> List[RequestInfo]:
    queue = Queue()
    results = []

    # Start the request creator and status checker tasks
    creator_task = asyncio.create_task(
        request_creator(user, user_no, example_contract, num_requests, queue)
    )
    checker_task = asyncio.create_task(status_checker(user, queue, results))

    # Wait for both tasks to complete
    await asyncio.gather(creator_task, checker_task)

    return results
