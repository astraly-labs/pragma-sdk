import asyncio
import logging
import sys
from typing import List, Optional

from starknet_py.contract import InvokeResult
from starknet_py.net.client import Client
from starknet_py.net.client_errors import ClientError

from pragma.core.abis import ABIS
from pragma.core.contract import Contract
from pragma.core.randomness.utils import (
    RandomnessRequest,
    create_randomness,
    felt_to_secret_key,
)
from pragma.core.types import RequestStatus

logger = logging.getLogger(__name__)

IGNORE_REQUEST_THRESHOLD = 30


class RandomnessMixin:
    client: Client
    randomness: Optional[Contract] = None

    def init_randomness_contract(self, contract_address: int):
        provider = self.account if self.account else self.client
        self.randomness = Contract(
            address=contract_address,
            abi=ABIS["pragma_Randomness"],
            provider=provider,
            cairo_version=1,
        )

    async def request_random(
        self,
        seed: int,
        callback_address: int,
        callback_fee_limit: int = 1000000,
        publish_delay: int = 1,
        num_words: int = 1,
        calldata: List[int] = None,
        max_fee=int(1e16),
    ) -> InvokeResult:
        if calldata is None:
            calldata = []
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["request_random"].invoke_v1(
            seed,
            callback_address,
            callback_fee_limit,
            publish_delay,
            num_words,
            calldata,
            max_fee=max_fee,
        )
        return invocation

    async def estimate_gas_request_random_op(
        self,
        seed: int,
        callback_address: int,
        callback_fee_limit: int = 1000000,
        publish_delay: int = 1,
        num_words: int = 1,
        calldata: List[int] = None,
        max_fee=int(1e16),
    ):
        if calldata is None:
            calldata = []
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["request_random"].prepare_invoke_v1(
            seed,
            callback_address,
            callback_fee_limit,
            publish_delay,
            num_words,
            calldata,
            max_fee=max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def estimate_gas_call(self, caller_address: int, method: str):
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions[method].prepare_invoke_v1(
            caller_address
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def submit_random(
        self,
        request_id: int,
        requestor_address: int,
        seed: int,
        callback_address: int,
        callback_fee_limit: int,  # =1000000
        minimum_block_number: int,
        random_words: List[int],  # List with 1 item
        proof: List[int],  # randomness proof,
        calldata: List[int],
        max_fee=int(1e16),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_fee_limit,
            callback_fee_limit,
            random_words,
            proof,
            calldata,
            max_fee=max_fee,
        )
        try:
            estimate_fee = await prepared_call.estimate_fee()
        except ClientError as e:
            print("Error while estimating fee: ", e)
            return None
        if estimate_fee.overall_fee > callback_fee_limit:
            logger.error(
                "OUT OF GAS %s > %s", estimate_fee.overall_fee, callback_fee_limit
            )
            invocation = await self.randomness.functions["update_status"].invoke_v1(
                requestor_address,
                request_id,
                RequestStatus.OUT_OF_GAS.serialize(),
                auto_estimate=True,
            )

            # Refund gas
            await self.refund_operation(request_id, requestor_address)
            return invocation

        invocation = await self.randomness.functions["submit_random"].invoke_v1(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_fee_limit,
            estimate_fee.overall_fee,
            random_words,
            proof,
            calldata,
            max_fee=max_fee,
        )
        logger.info("Sumbitted random %s", invocation.hash)
        return invocation

    async def estimate_gas_submit_random_op(
        self,
        request_id: int,
        requestor_address: int,
        seed: int,
        callback_address: int,
        callback_fee_limit: int,  # =1000000
        minimum_block_number: int,
        random_words: List[int],  # List with 1 item
        proof: List[int],  # randomness proof,
        calldata: List[int],
        max_fee=int(1e16),
    ):
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_fee_limit,
            callback_fee_limit,
            random_words,
            proof,
            calldata,
            max_fee=max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def estimate_gas_update_status_op(
        self,
        requestor_address,
        request_id,
    ):
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["update_status"].prepare_invoke_v1(
            requestor_address,
            request_id,
            RequestStatus.RECEIVED.serialize(),
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def get_request_status(
        self,
        caller_address: int,
        request_id: int,
    ):
        (response,) = await self.randomness.functions["get_request_status"].call(
            caller_address,
            request_id,
        )

        return response

    async def get_total_fees(self, caller_address: int, request_id: int):
        (response,) = await self.randomness.functions["get_total_fees"].call(
            caller_address, request_id
        )

        return response

    async def compute_premium_fee(self, caller_address: int):
        (response,) = await self.randomness.functions["compute_premium_fee"].call(
            caller_address
        )

        return response

    async def requestor_current_index(self, caller_address: int):
        (response,) = await self.randomness.functions["requestor_current_index"].call(
            caller_address
        )

        return response

    async def get_pending_requests(
        self,
        requestor_address: int,
        offset=0,
        max_len=100,
    ):
        (response,) = await self.randomness.functions["get_pending_requests"].call(
            requestor_address,
            offset,
            max_len,
        )

        return response

    async def cancel_random_request(
        self,
        request_id: int,
        requestor_address: int,
        seed: int,
        callback_address: int,
        callback_fee_limit: int,
        minimum_block_number: int,
        num_words: int,
        max_fee=int(1e16),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.randomness.functions["cancel_random_request"].invoke_v1(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_fee_limit,
            num_words,
            max_fee=max_fee,
        )
        return invocation

    async def estimate_gas_cancel_random_op(
        self,
        request_id: int,
        requestor_address: int,
        seed: int,
        callback_address: int,
        callback_fee_limit: int,
        minimum_block_number: int,
        num_words: int,
        max_fee=int(1e16),
    ):
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions[
            "cancel_random_request"
        ].prepare_invoke_v1(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_fee_limit,
            num_words,
            max_fee=max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def refund_operation(
        self,
        request_id: int,
        requestor_address: int,
        max_fee=int(1e16),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.randomness.functions["refund_operation"].invoke_v1(
            requestor_address, request_id, max_fee=max_fee
        )
        return invocation

    async def handle_random(
        self,
        private_key: int,
        min_block: int = 0,
    ):
        block_number = await self.full_node_client.get_block_number()

        min_block = max(min_block, block_number - IGNORE_REQUEST_THRESHOLD)

        sk = felt_to_secret_key(private_key)

        more_pages = True
        continuation_token = None

        # TODO(#000): add nonce tracking
        while more_pages:
            event_list = await self.full_node_client.get_events(
                self.randomness.address,
                keys=[
                    ["0xe3e1c077138abb6d570b1a7ba425f5479b12f50a78a72be680167d4cf79c48"]
                ],
                from_block_number=min_block,
                to_block_number="pending",
                continuation_token=continuation_token,
                chunk_size=500,
            )
            for event in event_list.events:
                index_to_split = 7
                event.data.pop(index_to_split)
                first_part = event.data[:index_to_split]
                second_part = event.data[index_to_split:]
                event.data = first_part + [second_part]
            events = [RandomnessRequest(*r.data) for r in event_list.events]
            continuation_token = event_list.continuation_token
            more_pages = continuation_token is not None

            for event in events:
                minimum_block_number = event.minimum_block_number
                # Skip if block_number is less than minimum_block_number
                # Take into account pending block
                # Ignore requests that are too old
                if (
                    minimum_block_number > block_number + 1
                    or minimum_block_number < block_number - IGNORE_REQUEST_THRESHOLD
                ):
                    continue
                request_id = event.request_id
                status = await self.get_request_status(event.caller_address, request_id)
                if status.variant != "RECEIVED":
                    continue

                print(f"event {event}")

                is_pending = minimum_block_number == block_number + 1

                block = (
                    await self.full_node_client.get_block(block_number="pending")
                    if is_pending
                    else await self.full_node_client.get_block(block_number="latest")
                )
                block_hash = block.parent_block_hash

                seed = (
                    event.request_id.to_bytes(8, sys.byteorder)
                    + block_hash.to_bytes(32, sys.byteorder)
                    + event.seed.to_bytes(32, sys.byteorder)
                    + event.caller_address.to_bytes(32, sys.byteorder)
                )
                beta_string, pi_string, _pub = create_randomness(sk, seed)
                beta_string = int.from_bytes(beta_string, sys.byteorder)
                proof = [
                    int.from_bytes(p, sys.byteorder)
                    for p in [pi_string[:31], pi_string[31:62], pi_string[62:]]
                ]

                random_words = [beta_string]

                invocation = await self.submit_random(
                    event.request_id,
                    event.caller_address,
                    event.seed,
                    event.callback_address,
                    event.callback_fee_limit,
                    event.minimum_block_number,
                    random_words,
                    proof,
                    event.calldata,
                )

                if invocation is None:
                    print("Failed to submit random")
                    continue

                print(f"Submitted: {hex(invocation.hash)}\n\n")

                # Wait for Tx to pass
                await asyncio.sleep(5)
