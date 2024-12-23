import logging

from typing import Optional

from grpc import ssl_channel_credentials
from grpc.aio import secure_channel
from apibara.protocol import StreamAddress, StreamService, credentials_with_auth_token
from apibara.protocol.proto.stream_pb2 import DataFinality
from apibara.starknet import Block, EventFilter, Filter, felt, starknet_cursor

from pragma_sdk.onchain.types import RandomnessRequest
from pragma_sdk.onchain.constants import RANDOMNESS_REQUEST_EVENT_SELECTOR
from pragma_sdk.onchain.client import PragmaOnChainClient

from vrf_listener.safe_queue import ThreadSafeQueue

EVENT_INDEX_TO_SPLIT = 7

logger = logging.getLogger(__name__)


class Indexer:
    stream: StreamService
    requests_queue: ThreadSafeQueue

    def __init__(
        self,
        stream: StreamService,
        requests_queue: ThreadSafeQueue,
    ) -> None:
        self.stream = stream
        self.requests_queue = requests_queue

    @classmethod
    async def from_client(
        cls,
        pragma_client: PragmaOnChainClient,
        apibara_api_key: Optional[str],
        requests_queue: ThreadSafeQueue,
        from_block: Optional[int] = None,
    ):
        """
        Creates an Indexer from a PragmaOnChainClient.
        """
        if apibara_api_key is None:
            raise ValueError("--apibara-api-key not provided.")

        channel = secure_channel(
            StreamAddress.StarkNet.Sepolia
            if pragma_client.network == "sepolia"
            else StreamAddress.StarkNet.Mainnet,
            credentials_with_auth_token(apibara_api_key, ssl_channel_credentials()),
        )
        filter = (
            Filter()
            .with_header(weak=False)
            .add_event(
                EventFilter()
                .with_from_address(felt.from_int(pragma_client.randomness.address))
                .with_keys([felt.from_hex(RANDOMNESS_REQUEST_EVENT_SELECTOR)])
                .with_include_receipt(False)
                .with_include_transaction(False)
            )
            .encode()
        )
        if from_block:
            current_block = from_block
        else:
            current_block = await pragma_client.get_block_number()

        stream = StreamService(channel).stream_data_immutable(
            filter=filter,
            finality=DataFinality.DATA_STATUS_PENDING,
            batch_size=1,
            cursor=starknet_cursor(current_block),
        )
        return cls(stream=stream, requests_queue=requests_queue)

    async def run_forever(self) -> None:
        """
        Index forever using Apibara and fill the requests_queue when encountering a
        VRF request.
        """
        logger.info("👩‍💻 Indexing VRF requests using apibara...")
        block = Block()
        async for message in self.stream:
            if message.data is None:
                continue
            for batch in message.data.data:
                block.ParseFromString(batch)
                if len(block.events) == 0:
                    continue
                events = block.events
                for event in events:
                    data = list(map(felt.to_int, event.event.data))
                    data = data[:EVENT_INDEX_TO_SPLIT] + [
                        data[EVENT_INDEX_TO_SPLIT + 1 :]
                    ]
                    await self.requests_queue.put(RandomnessRequest(*data))
