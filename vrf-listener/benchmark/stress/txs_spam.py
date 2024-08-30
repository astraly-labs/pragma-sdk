import asyncio

from typing import List
from dataclasses import dataclass
from datetime import datetime
from asyncio import Queue

from starknet_py.contract import Contract, TypeSentTransaction

from pragma_sdk.onchain.types import (
    VRFRequestParams,
    RequestStatus,
)

from benchmark.client import ExtendedPragmaClient

# Time to wait between request status check (in secs)
TTW_BETWEEN_REQ_CHECK = 0.5


@dataclass
class RequestInfo:
    tx_hash: str
    sent_tx: TypeSentTransaction
    request_time: datetime
    request_id: int = None
    fulfillment_time: datetime = None


async def get_request_id(
    user: ExtendedPragmaClient,
    tx_hash: str,
) -> int:
    """
    Retrieve the request_id in the transaction receipt of a request.
    """
    receipt = await user.full_node_client.get_transaction_receipt(tx_hash=tx_hash)
    request_id = receipt.events[2].data[0]
    return request_id


async def create_request(
    user: ExtendedPragmaClient,
    example_contract: Contract,
) -> RequestInfo:
    """
    Create a VRF request with the provided user using the example_contract as callback.
    """
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
    request_id = await get_request_id(user, invocation.hash)
    await invocation.wait_for_acceptance()
    return RequestInfo(
        request_id=request_id,
        tx_hash=invocation.hash,
        sent_tx=invocation,
        request_time=datetime.now(),
    )


async def check_request_status(
    user: ExtendedPragmaClient,
    request_info: RequestInfo,
) -> None:
    """
    Check forever the status of the provided request until it is FULFILLED.
    """
    while True:
        status = await user.get_request_status(
            caller_address=user.account.address,
            request_id=request_info.request_id,
            block_id="pending",
        )
        if status == RequestStatus.FULFILLED or status == RequestStatus.REFUNDED:
            request_info.fulfillment_time = datetime.now()
            break
        await asyncio.sleep(TTW_BETWEEN_REQ_CHECK)


async def request_creator(
    user: ExtendedPragmaClient,
    example_contract: Contract,
    num_requests: int,
    queue: Queue,
) -> None:
    """
    Creates N VRF requests using the provided user & put them into the check queue.
    """
    for _ in range(num_requests):
        request_info = await create_request(user, example_contract)
        await queue.put(request_info)
    await queue.put(None)  # Signal that we're done creating requests


async def status_checker(
    user: ExtendedPragmaClient,
    queue: Queue,
    results: List[RequestInfo],
) -> None:
    """
    Reads the provided queue that will be filled with VRF Requests & check their status.
    """
    while True:
        request_info = await queue.get()
        if request_info is None:
            break
        await check_request_status(user, request_info)
        results.append(request_info)


async def spam_reqs_with_user(
    user: ExtendedPragmaClient,
    example_contract: Contract,
    txs_per_user: int,
) -> List[RequestInfo]:
    """
    Given a User client, spams [num_requests] requests.
    """
    queue = Queue()
    results = []

    # Start the request creator and status checker tasks
    creator_task = asyncio.create_task(request_creator(user, example_contract, txs_per_user, queue))
    checker_task = asyncio.create_task(status_checker(user, queue, results))

    # Wait for both tasks to complete
    await asyncio.gather(creator_task, checker_task)

    return results
