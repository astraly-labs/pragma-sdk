import time
from typing import Callable, Coroutine, Dict, List, Optional

from deprecated import deprecated
from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client


from pragma_sdk.onchain.types import Contract
from pragma_sdk.common.types.entry import Entry, FutureEntry, SpotEntry
from pragma_sdk.common.logging import get_stream_logger

from pragma_sdk.common.types.types import AggregationMode
from pragma_sdk.common.types.asset import Asset
from pragma_sdk.common.types.types import DataTypes, Address, Decimals, ExecutionConfig
from pragma_sdk.common.types.pair import Pair

from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.onchain.types import OracleResponse

logger = get_stream_logger()


class OracleMixin:
    publisher_registry: Contract
    client: Client
    account: Account
    execution_config: ExecutionConfig
    oracle: Contract
    is_user_client: bool = False
    track_nonce: Callable[[object, int, int], Coroutine[None, None, None]]

    @deprecated
    async def publish_spot_entry(
        self,
        pair_id: int,
        value: int,
        timestamp: int,
        source: int,
        publisher: int,
        volume: int = 0,
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.oracle.functions["publish_data"].invoke(
            new_entry={
                "Spot": {
                    "base": {
                        "timestamp": timestamp,
                        "source": source,
                        "publisher": publisher,
                    },
                    "price": value,
                    "pair_id": pair_id,
                    "volume": volume,
                }
            },
            execution_config=self.execution_config,
        )
        return invocation

    async def publish_many(
        self,
        entries: List[Entry],
        execution_config: ExecutionConfig,
    ) -> List[InvokeResult]:
        if not entries:
            logger.warning("Skipping publishing as entries array is empty")
            return []

        invocations: List[InvokeResult] = []

        spot_entries: List[Entry] = [
            entry for entry in entries if isinstance(entry, SpotEntry)
        ]
        future_entries: List[Entry] = [
            entry for entry in entries if isinstance(entry, FutureEntry)
        ]

        invocations.extend(
            await self._publish_entries(spot_entries, DataTypes.SPOT, execution_config)
        )
        invocations.extend(
            await self._publish_entries(
                future_entries, DataTypes.FUTURE, execution_config
            )
        )

        return invocations

    async def _publish_entries(
        self, entries: List[Entry], data_type: DataTypes, config: ExecutionConfig
    ) -> List[InvokeResult]:
        invocations = []
        serialized_entries = (
            SpotEntry.serialize_entries(entries)
            if data_type == DataTypes.SPOT
            else FutureEntry.serialize_entries(entries)
        )

        if len(serialized_entries) == 0:
            return []

        if config.pagination:
            for i in range(0, len(serialized_entries), config.pagination):
                entries_subset = serialized_entries[i : i + config.pagination]
                invocation = await self._invoke_publish(
                    entries_subset, data_type, config
                )
                invocations.append(invocation)
                self._log_transaction(invocation, len(entries_subset), data_type)
        else:
            invocation = await self._invoke_publish(
                serialized_entries, data_type, config
            )
            invocations.append(invocation)
            self._log_transaction(invocation, len(serialized_entries), data_type)

        return invocations

    async def _invoke_publish(
        self, entries: List[Dict], data_type: DataTypes, config: ExecutionConfig
    ) -> InvokeResult:
        return await self.oracle.functions["publish_data_entries"].invoke(
            new_entries=[{data_type: entry} for entry in entries],
            execution_config=config,
            callback=self.track_nonce,
        )

    def _log_transaction(
        self, invocation: InvokeResult, entry_count: int, data_type: DataTypes
    ):
        logger.debug(hex(invocation.hash))
        logger.info(
            f"Sent {entry_count} updated {data_type.name.lower()} entries with transaction {hex(invocation.hash)}"
        )

    @deprecated
    async def get_spot_entries(
        self, pair_id, sources=None, block_number="latest"
    ) -> List[SpotEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            Asset(DataTypes.SPOT, pair_id, None).serialize(),
            sources,
            block_number=block_number,
        )
        entries = response[0]
        return [SpotEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_all_sources(self, asset: Asset, block_number="latest") -> List[str]:
        """
        Query on-chain all sources used for a given asset.

        :param asset: Asset
        :param block_number: Block number or Block Tag
        :return: List of sources
        """
        (response,) = await self.oracle.functions["get_all_sources"].call(
            asset.serialize(), block_number=block_number
        )

        return [felt_to_str(source) for source in response]

    @deprecated
    async def get_future_entries(
        self, pair_id, expiration_timestamp, sources=None, block_number="latest"
    ) -> List[FutureEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            Asset(DataTypes.FUTURE, pair_id, expiration_timestamp).serialize(),
            sources,
            block_number=block_number,
        )
        entries = response[0]
        return [FutureEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_spot(
        self,
        pair_id: str | int,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources: Optional[List[str | int]] = None,
        block_number="latest",
    ) -> OracleResponse:
        """
        Query the Oracle contract for the data of a spot asset.

        :param pair_id: Pair ID
        :param aggregation_mode: AggregationMode
        :param sources: List of sources, if None will use all sources
        :param block_number: Block number or Block Tag
        :return: OracleResponse
        """
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                Asset(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
                block_number=block_number,
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                Asset(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
                sources,
                block_number=block_number,
            )

        response = dict(response)

        return OracleResponse(
            response["price"],
            response["decimals"],
            response["last_updated_timestamp"],
            response["num_sources_aggregated"],
            response["expiration_timestamp"],
        )

    async def get_future(
        self,
        pair_id: str | int,
        expiry_timestamp: int,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources: Optional[List[str | int]] = None,
        block_number="latest",
    ) -> OracleResponse:
        """
        Query the Oracle contract for the data of a future asset.

        :param pair_id: Pair ID
        :param expiry_timestamp: Expiry timestamp of the future contract
        :param aggregation_mode: AggregationMode
        :param sources: List of sources, if None will use all sources
        :param block_number: Block number or Block Tag
        :return: OracleResponse
        """
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                Asset(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
                block_number=block_number,
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                Asset(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
                sources,
                block_number=block_number,
            )

        response = dict(response)

        return OracleResponse(
            response["price"],
            response["decimals"],
            response["last_updated_timestamp"],
            response["num_sources_aggregated"],
            response["expiration_timestamp"],
        )

    async def get_decimals(self, asset: Asset, block_number="latest") -> Decimals:
        """
        Query on-chain the decimals for a given asset

        :param asset: Asset
        :param block_number: Block number or Block Tag
        :return: Decimals
        """
        (response,) = await self.oracle.functions["get_decimals"].call(
            asset.serialize(),
            block_number=block_number,
        )

        return response  # type: ignore[no-any-return]

    # TODO (#000): Fix future checkpoints
    async def set_future_checkpoints(
        self,
        pair_ids: List[int],
        expiry_timestamps: List[int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = None
        if self.execution_config.pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[
                    index : index + self.execution_config.pagination
                ]
                invocation = await self.oracle.functions["set_checkpoints"].invoke(
                    pair_ids_subset,
                    expiry_timestamps,
                    aggregation_mode.serialize(),
                    max_fee=self.execution_config.max_fee,
                )
                index += self.execution_config.pagination
                logger.debug(hex(invocation.hash))
                logger.info(
                    "Set future checkpoints for %d pair IDs with transaction %s",
                    len(pair_ids_subset),
                    hex(invocation.hash),
                )
        else:
            invocation = await self.oracle.functions["set_checkpoints"].invoke(
                pair_ids,
                expiry_timestamps,
                aggregation_mode.serialize(),
                max_fee=self.execution_config.max_fee,
            )

        return invocation

    async def set_checkpoints(
        self,
        pair_ids: List[str | int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
    ) -> InvokeResult:
        """
        Set checkpoints for a list of pair IDs.

        :param pair_ids: List of pair IDs
        :param aggregation_mode: AggregationMode
        :param execution_config: ExecutionConfig
        :return: InvokeResult
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = None
        if self.execution_config.pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[
                    index : index + self.execution_config.pagination
                ]
                invocation = await self.oracle.set_checkpoints.invoke(
                    [
                        Asset(DataTypes.SPOT, pair_id, None).serialize()
                        for pair_id in pair_ids_subset
                    ],
                    aggregation_mode.serialize(),
                    max_fee=self.execution_config.max_fee,
                )
                index += self.execution_config.pagination
                logger.debug(hex(invocation.hash))
                logger.info(
                    "Set checkpoints for %d pair IDs with transaction %s",
                    len(pair_ids_subset),
                    hex(invocation.hash),
                )
        else:
            invocation = await self.oracle.set_checkpoints.invoke(
                [
                    Asset(DataTypes.SPOT, pair_id, None).serialize()
                    for pair_id in pair_ids
                ],
                aggregation_mode.serialize(),
                max_fee=self.execution_config.max_fee,
            )

        return invocation

    async def get_admin_address(self) -> Address:
        """
        Return the admin address of the Oracle contract.
        """

        (response,) = await self.oracle.functions["get_admin_address"].call()
        return response  # type: ignore[no-any-return]

    async def update_oracle(
        self,
        implementation_hash: int,
    ) -> InvokeResult:
        """
        Update the Oracle contract to a new implementation.

        :param implementation_hash: New implementation hash
        :param execution_config: ExecutionConfig
        :return: InvokeResult
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.oracle.functions["upgrade"].invoke(
            implementation_hash,
            max_fee=self.execution_config.max_fee,
        )
        return invocation

    async def get_time_since_last_published_spot(
        self, pair: Pair, publisher: str, block_number="latest"
    ) -> int:
        """
        Get the time since the last published spot entry by a publisher for a given pair.
        Will return a large number if no entry is found.

        :param pair: Pair
        :param publisher: Publisher name e.g "PRAGMA"
        :param block_number: Block number or Block Tag
        :return: Time since last published entry
        """
        all_entries = await self.get_spot_entries(pair.id, block_number=block_number)

        entries = [
            entry
            for entry in all_entries
            if entry.base.publisher == str_to_felt(publisher)
        ]

        if len(entries) == 0:
            return 1000000000  # arbitrary large number

        max_timestamp = max(entry.base.timestamp for entry in entries)

        diff = int(time.time()) - max_timestamp

        return diff
