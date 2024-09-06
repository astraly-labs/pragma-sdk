import asyncio
import sys
import multiprocessing
import time

from typing import List, Optional, Tuple, Any, Set

from starknet_py.contract import InvokeResult
from starknet_py.net.client import Client, Call
from starknet_py.net.client_models import EstimatedFee
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.account.account import Account

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.randomness.utils import (
    create_randomness,
    felt_to_secret_key,
)
from pragma_sdk.common.types.types import Address

from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.types import RequestStatus, RandomnessRequest
from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.onchain.constants import RANDOMNESS_REQUEST_EVENT_SELECTOR
from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.types import (
    VRFCancelParams,
    VRFRequestParams,
    VRFSubmitParams,
)
from pragma_sdk.onchain.types.types import BlockId

logger = get_pragma_sdk_logger()


class RandomnessMixin:
    client: Client
    account: Optional[Account] = None
    randomness: Contract
    is_user_client: bool = False
    full_node_client: FullNodeClient
    execution_config: ExecutionConfig

    def init_randomness_contract(self, contract_address: Address):
        """
        Init the [`randomness`] class parameter for the VRF contract with the provided address.
        """
        provider = self.account if self.account else self.client
        self.randomness = Contract(
            address=contract_address,
            abi=ABIS["pragma_Randomness"],
            provider=provider,
            cairo_version=1,
        )

    async def request_random(
        self,
        request_params: VRFRequestParams,
    ) -> InvokeResult:
        """
        Request randomness from the VRF contract.
        Must set account. You may do this by invoking self._setup_account_client(private_key, account_contract_address)

        :param request_params: VRFRequestParams object containing the request parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if request_params.calldata is None:
            request_params.calldata = []

        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["request_random"].invoke(
            *request_params.to_list(),
            execution_config=self.execution_config,
        )
        return invocation

    async def estimate_gas_request_random_op(
        self,
        vrf_request_params: VRFRequestParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the request_random operation.

        :param vrf_request_params: VRFRequestParams object containing the request parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if vrf_request_params.calldata is None:
            vrf_request_params.calldata = []

        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["request_random"].prepare_invoke_v1(
            *vrf_request_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def _get_submit_or_refund_calls(
        self,
        request: VRFSubmitParams,
        is_whitelisted: bool = False,
    ) -> List[Call]:
        """
        Returns a Sequence of Call necesary to either submit or refund the provided
        request.

        If the caller is whitelisted, we don't check if there's enough fees for the call
        to work. We will pay for the fees if there isn't enough.
        """
        submit_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            *request.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        if is_whitelisted:
            return [submit_call]

        estimate_fee = await submit_call.estimate_fee(block_number="pending")
        if estimate_fee.overall_fee <= request.callback_fee_limit:
            return [submit_call]

        logger.error(
            "Request %s is OUT OF GAS: %s > %s - cancelled & refunded.",
            request.request_id,
            estimate_fee.overall_fee,
            request.callback_fee_limit,
        )
        update_status_call = self.randomness.functions[
            "update_status"
        ].prepare_invoke_v1(
            request.requestor_address,
            request.request_id,
            RequestStatus.OUT_OF_GAS.serialize(),
            max_fee=self.execution_config.max_fee,
        )
        refund_call = self.randomness.functions["refund_operation"].prepare_invoke_v1(
            request.requestor_address,
            request.request_id,
            max_fee=self.execution_config.max_fee,
        )
        return [update_status_call, refund_call]

    async def submit_random_multicall(
        self,
        vrf_requests: List[VRFSubmitParams],
        whitelisted_addresses: Set[Address],
    ) -> InvokeResult:
        """
        Submit randomness to the VRF contract using a multicall.

        If fee estimation fails, the status of the request is updated to OUT_OF_GAS.
        Then, the remaining gas is refunded to the requestor address.

        For callers that are in the whitelisted_addresses set, we won't check if they
        have enough ETH for the callback fees.

        Fee estimation is used to set the callback fee parameter in the VRFSubmitParams object.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        timer_before_calls = time.time()
        all_calls = await asyncio.gather(
            *[
                self._get_submit_or_refund_calls(
                    request=request,
                    is_whitelisted=request.requestor_address in whitelisted_addresses,
                )
                for request in vrf_requests
            ]
        )
        all_calls = flatten_list(all_calls)
        logger.info(f"Call creation took: {(time.time()) - timer_before_calls:02f}s")

        invocation = await self.randomness.multicall(
            prepared_calls=all_calls,
            execution_config=self.execution_config,
        )
        await self.full_node_client.wait_for_tx(
            tx_hash=invocation.hash,
            check_interval=0.5,
        )
        return invocation

    async def estimate_gas_submit_random_op(
        self,
        vrf_submit_params: VRFSubmitParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the submit_random operation.

        :param vrf_submit_params: VRFSubmitParams object containing the submit parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        vrf_submit_params.callback_fee = vrf_submit_params.callback_fee_limit

        prepared_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            *vrf_submit_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def get_request_status(
        self,
        caller_address: Address,
        request_id: int,
        block_id: Optional[BlockId] = "pending",
    ) -> RequestStatus:
        """
        Query the status of a request given the caller address and request ID.

        :param caller_address: The caller address.
        :param request_id: The request ID.
        :return: The status of the request.
        """
        (response,) = await self.randomness.functions["get_request_status"].call(
            caller_address,
            request_id,
            block_number=block_id,
        )
        return RequestStatus(response.variant)

    async def get_total_fees(self, caller_address: Address, request_id: int) -> int:
        """
        Query the total fees of a request given the caller address and request ID.
        Total fees correspond to the sum of the callback fee and the premium fee.

        :param caller_address: The caller address.
        :param request_id: The request ID.
        :return: The total fees of the request.
        """
        (response,) = await self.randomness.functions["get_total_fees"].call(
            caller_address, request_id
        )

        return response  # type: ignore[no-any-return]

    async def compute_premium_fee(self, caller_address: Address) -> int:
        """
        Query the premium fee for a request given the caller address.
        see https://docs.pragma.build/Resources/Cairo%201/randomness/randomness#pricing

        :param caller_address: The caller address.
        :return: The premium fee.
        """
        (response,) = await self.randomness.functions["compute_premium_fee"].call(
            caller_address
        )

        return response  # type: ignore[no-any-return]

    async def requestor_current_request_id(self, caller_address: Address) -> int:
        """
        Query the request id of the latest request made by the caller address.

        :param caller_address: The caller address.
        :return: The request id of the latest request.
        """
        (response,) = await self.randomness.functions["requestor_current_index"].call(
            caller_address
        )

        return response  # type: ignore[no-any-return]

    async def get_pending_requests(
        self,
        requestor_address: Address,
        offset: int = 0,
        max_len: int = 100,
    ) -> List[int]:
        """
        Query the pending requests of a requestor address.

        :param requestor_address: The requestor address.
        :param offset: Request id from which to start the query.
        :param max_len: Maximum number of requests to query.
        :return: The pending requests of the requestor address.
        """
        (response,) = await self.randomness.functions["get_pending_requests"].call(
            requestor_address,
            offset,
            max_len,
        )

        return response  # type: ignore[no-any-return]

    async def cancel_random_request(
        self,
        vrf_cancel_params: VRFCancelParams,
    ) -> InvokeResult:
        """
        Cancel a random request given the request parameters.
        see more info https://docs.pragma.build/Resources/Cairo%201/randomness/randomness#function-cancel_random_request

        :param vrf_cancel_params: VRFCancelParams object containing the cancel parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["cancel_random_request"].invoke(
            *vrf_cancel_params.to_list(),
            execution_config=self.execution_config,
        )
        return invocation

    async def estimate_gas_cancel_random_op(
        self,
        vrf_cancel_params: VRFCancelParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the cancel_random_request operation.

        :param vrf_cancel_params: VRFCancelParams object containing the cancel parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        prepared_call = self.randomness.functions[
            "cancel_random_request"
        ].prepare_invoke_v1(
            *vrf_cancel_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee  # type: ignore[no-any-return]

    async def refund_operation(
        self,
        request_id: int,
        requestor_address: int,
    ) -> InvokeResult:
        """
        Refund the remaining gas to the requestor address.
        Only requests with status OUT_OF_GAS can be refunded.

        :param request_id: The request ID.
        :param requestor_address: The requestor address.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["refund_operation"].invoke(
            requestor_address, request_id, execution_config=self.execution_config
        )

        return invocation

    async def _index_randomness_requests_events(
        self,
        from_block: int,
        to_block: BlockId = "pending",
        chunk_size: int = 512,
    ) -> List[RandomnessRequest]:
        """
        Indexes all the Randomness request events from the [from_block] block
        to [to_block] and returns them.
        """
        more_pages = True
        continuation_token = None
        requests_events = []

        while more_pages:
            event_list = await self.full_node_client.get_events(
                self.randomness.address,
                keys=[[RANDOMNESS_REQUEST_EVENT_SELECTOR]],
                from_block_number=from_block,
                to_block_number=to_block,
                continuation_token=continuation_token,
                chunk_size=512,
            )

            # Remove the calldata length from the event data
            for event in event_list.events:
                index_to_split = 7
                event.data = event.data[:index_to_split] + [
                    event.data[index_to_split + 1 :]
                ]

            requests_events.extend(
                [RandomnessRequest(*r.data) for r in event_list.events]
            )

            continuation_token = event_list.continuation_token
            more_pages = continuation_token is not None

        return requests_events

    async def handle_random(
        self,
        private_key: int,
        ignore_request_threshold: int = 3,
        requests_events: Optional[List[RandomnessRequest]] = None,
        whitelisted_addresses: Set[Address] = set(),
    ) -> None:
        """
        Handle randomness requests.
        Will submit randomness for requests that are not too old and have not been handled yet.

        The steps are:
            1. Index the RandomnessRequest events if they're not provided in the [requests_events]
               parameter,
            2. Fetch the status of the requests & only keep the RECEIVED requests,
            3. Fetch the block hash of each events,
            4. Compute the VRF submissions of all events,
            5. Submit all the submissions through a multicall in [submit_random_multicall].
        """
        block_number = await self.full_node_client.get_block_number()
        min_block = max(block_number - ignore_request_threshold, 0)
        logger.debug(f"Handle random job running with min_block: {min_block}")

        # We either retrieve the [requests_events] provided events or index ourselves
        # the request events.
        if requests_events is None:
            events = await self._index_randomness_requests_events(
                from_block=min_block,
                to_block="pending",
            )
        else:
            events = requests_events

        if len(events) == 0:
            return

        # TODO: Keep in memory the request status so we don't re-request over
        # & over the same requests.
        # We only keep the RECEIVED requests.
        statuses = await asyncio.gather(
            *(
                self.get_request_status(
                    event.caller_address,
                    event.request_id,
                    block_id="pending",
                )
                for event in events
            )
        )
        filtered: List[Tuple[RequestStatus, RandomnessRequest]] = [
            (status, event)
            for status, event in zip(statuses, events)
            if status == RequestStatus.RECEIVED
        ]
        if not filtered:
            return

        statuses, events = zip(*filtered)  # type: ignore[assignment]
        logger.debug(f"Got {len(events)} RECEIVED events to process")

        block_hashes = await self.fetch_block_hashes(
            events=events,
            block_number=block_number,
            ignore_request_threshold=ignore_request_threshold,
        )

        vrf_submit_requests = self._compute_all_vrf_submit(
            events=events,
            block_hashes=block_hashes,
            sk=felt_to_secret_key(private_key),
        )

        timer_send_tx = time.time()
        invoke_tx = await self.submit_random_multicall(
            vrf_requests=vrf_submit_requests,
            whitelisted_addresses=whitelisted_addresses,
        )
        logger.info(f"Send tx took: {(time.time()) - timer_send_tx:02f}s")
        if not invoke_tx:
            logger.error(f"⛔ VRF Submission for {len(events)} failed!")
        else:
            logger.info(
                f"✅ Submitted the VRF responses for {len(events)} requests:"
                f" {hex(invoke_tx.hash)}"
            )

    async def fetch_block_hashes(
        self,
        events: List[RandomnessRequest],
        block_number: int,
        ignore_request_threshold: int,
    ) -> List[int | None]:
        """
        Fetch the block_hash of all events in parallel.
        --
        TODO: Really not optimal but not a bottleneck at the moment.
        We should be fetching only pending + latest and attribute that to
        the events, instead of doing N times (n = len of events).
        """

        async def get_block_hash(minimum_block_number: int) -> Optional[int]:
            if (
                minimum_block_number > block_number + 1
                or minimum_block_number < block_number - ignore_request_threshold
            ):
                return None

            is_pending = minimum_block_number == block_number + 1
            block = await self.full_node_client.get_block(
                block_number="pending" if is_pending else "latest"
            )
            return block.parent_hash  # type: ignore[no-any-return]

        block_hashes = await asyncio.gather(
            *[get_block_hash(event.minimum_block_number) for event in events]
        )
        return [hash for hash in block_hashes]

    def _compute_all_vrf_submit(
        self,
        events: List[RandomnessRequest],
        block_hashes: List[int | None],
        sk: bytes,
    ) -> List[VRFSubmitParams]:
        """
        Generate all the VRFSubmitParams requests that will be handled.
        """
        all_create_randomness_args = [
            (event, block_hash, sk)
            for event, block_hash in zip(events, block_hashes)
            if block_hash is not None
        ]
        # Spawn all the computations for all requests in different process instead
        # of doing it sequentially in one.
        with multiprocessing.Pool() as pool:
            vrf_submit_requests = pool.map(
                RandomnessMixin._create_randomness_for_event,
                all_create_randomness_args,
            )
        return [req for req in vrf_submit_requests]

    @staticmethod
    def _create_randomness_for_event(
        args: Tuple[RandomnessRequest, int, bytes],
    ) -> VRFSubmitParams:
        """
        Create the randomness submit params for the provided event request.
        """
        event, block_hash, sk = args

        seed = RandomnessMixin._build_request_seed(event, block_hash)
        beta_string, pi_string, _ = create_randomness(sk, seed)
        beta_string = int.from_bytes(beta_string, sys.byteorder)  # type: ignore[assignment, arg-type]
        proof = [
            int.from_bytes(p, sys.byteorder)  # type: ignore[arg-type]
            for p in [pi_string[:31], pi_string[31:62], pi_string[62:]]
        ]
        random_words: List[int] = [beta_string]  # type: ignore[list-item]

        return VRFSubmitParams(
            request_id=event.request_id,
            requestor_address=event.caller_address,
            seed=event.seed,
            minimum_block_number=event.minimum_block_number,
            callback_address=event.callback_address,
            callback_fee_limit=event.callback_fee_limit,
            random_words=random_words,
            proof=proof,
            calldata=event.calldata,
        )

    @staticmethod
    def _build_request_seed(event: RandomnessRequest, block_hash: int) -> bytes:
        """
        Builds the seed of a given RandomnessRequest for a block_hash.
        """
        return (
            event.request_id.to_bytes(8, sys.byteorder)  # type: ignore[return-value]
            + block_hash.to_bytes(32, sys.byteorder)
            + event.seed.to_bytes(32, sys.byteorder)
            + event.caller_address.to_bytes(32, sys.byteorder)
        )


def flatten_list(nested_list: list[Any] | tuple[Any, ...]) -> List:
    flattened = []
    for item in nested_list:
        if isinstance(item, (list, tuple)):
            flattened.extend(flatten_list(item))
        else:
            flattened.append(item)
    return flattened
