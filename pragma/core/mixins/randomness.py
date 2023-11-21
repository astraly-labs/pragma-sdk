import logging
import sys
from typing import Any, Callable, List, Optional
import asyncio

from starknet_py.contract import InvokeResult
from starknet_py.net.client import Client
from starknet_py.net.full_node_client import FullNodeClient

from pragma.core.abis import ABIS
from pragma.core.contract import Contract
from pragma.core.randomness.utils import (
    RandomnessRequest,
    create_randomness,
    felt_to_secret_key,
)

logger = logging.getLogger(__name__)


class RandomnessMixin:
    client: Client
    randomness: Optional[Contract] = None

    def init_randomness_contract(
        self,
        contract_address: int,
    ):
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
        callback_gas_limit: int = 1000000,
        publish_delay: int = 1,
        num_words: int = 1,
        max_fee=int(1e16),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by invoking self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.randomness.functions["request_random"].invoke(
            seed,
            callback_address,
            callback_gas_limit,
            publish_delay,
            num_words,
            max_fee=max_fee,
        )
        return invocation

    async def submit_random(
        self,
        request_id: int,
        requestor_address: int,
        seed: int,
        callback_address: int,
        callback_gas_limit: int,  # =1000000
        minimum_block_number: int,
        random_words: List[int],  # List with 1 item
        proof: List[int],  # randomness proof
        max_fee=int(1e16),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by invoking self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.randomness.functions["submit_random"].invoke(
            request_id,
            requestor_address,
            seed,
            minimum_block_number,
            callback_address,
            callback_gas_limit,
            random_words,
            proof,
            max_fee=max_fee,
        )
        return invocation

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

    async def handle_random(self, private_key: int, min_block: int = 0):
        block_number = await self.full_node_client.get_block_number()
        sk = felt_to_secret_key(private_key)

        more_pages = True
        continuation_token = None

        # TODO(#000): add nonce tracking
        while more_pages:
            event_list = await self.full_node_client.get_events(
                self.randomness.address,
                keys=[["0xe3e1c077138abb6d570b1a7ba425f5479b12f50a78a72be680167d4cf79c48"]],
                from_block_number=min_block,
                to_block_number=block_number,
                continuation_token=continuation_token,
                chunk_size=50,
            )
            events = [RandomnessRequest(*r.data) for r in event_list.events]
            continuation_token = event_list.continuation_token
            more_pages = continuation_token is not None

            for event in events:
                minimum_block_number = event.minimum_block_number
                if minimum_block_number > block_number:
                    continue
                request_id = event.request_id
                status = await self.get_request_status(event.caller_address, request_id)
                if status.variant != 'RECEIVED':
                    continue

                print(f"event {event}")

                block = await self.full_node_client.get_block(
                    block_number=minimum_block_number
                )
                block_hash = block.block_hash

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
                    event.callback_gas_limit,
                    event.minimum_block_number,
                    random_words,
                    proof,
                )

                print(f"submitted: {invocation.hash}\n\n")

                # Wait for Tx to pass
                await asyncio.sleep(5)
