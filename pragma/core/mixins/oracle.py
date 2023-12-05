import collections
import logging
from typing import List, Optional

from deprecated import deprecated
from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client

from pragma.core.contract import Contract
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.core.types import AggregationMode, DataType, DataTypes
from pragma.core.utils import felt_to_str, str_to_felt

logger = logging.getLogger(__name__)

OracleResponse = collections.namedtuple(
    "OracleResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)


class OracleMixin:
    publisher_registry: Contract
    client: Client
    account: Account

    @deprecated
    async def publish_spot_entry(
        self,
        pair_id: int,
        value: int,
        timestamp: int,
        source: int,
        publisher: int,
        volume: int = 0,
        max_fee: int = int(1e18),
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
            max_fee=max_fee,
        )
        return invocation

    async def publish_many(
        self,
        entries: List[Entry],
        pagination: Optional[int] = 40,
        max_fee=int(1e18),
    ) -> List[InvokeResult]:
        if len(entries) == 0:
            logger.warning("Skipping publishing as entries array is empty")
            return

        invocations = []
        serialized_spot_entries = SpotEntry.serialize_entries(entries)
        if pagination:
            index = 0
            while index < len(serialized_spot_entries):
                entries_subset = serialized_spot_entries[index : index + pagination]
                invocation = await self.oracle.functions["publish_data_entries"].invoke(
                    new_entries=[{"Spot": entry} for entry in entries_subset],
                    max_fee=max_fee,
                )
                index += pagination
                invocations.append(invocation)
                logger.debug(str(invocation))
                logger.info(
                    "Sent %d updated spot entries with transaction %s",
                    len(entries_subset),
                    hex(invocation.hash),
                )
        elif len(serialized_spot_entries) > 0:
            invocation = await self.oracle.functions["publish_data_entries"].invoke(
                new_entries=[{"Spot": entry} for entry in serialized_spot_entries],
                max_fee=max_fee,
            )
            invocations.append(invocation)
            logger.debug(str(invocation))
            logger.info(
                "Sent %d updated spot entries with transaction %s",
                len(serialized_spot_entries),
                hex(invocation.hash),
            )

        serialized_future_entries = FutureEntry.serialize_entries(entries)
        if pagination:
            index = 0
            while index < len(serialized_future_entries):
                entries_subset = serialized_future_entries[index : index + pagination]
                invocation = await self.oracle.functions["publish_data_entries"].invoke(
                    new_entries=[{"Future": entry} for entry in entries_subset],
                    max_fee=max_fee,
                )
                index += pagination
                invocations.append(invocation)
                logger.debug(str(invocation))
                logger.info(
                    "Sent %d updated future entries with transaction %s",
                    len(entries_subset),
                    hex(invocation.hash),
                )
        elif len(serialized_future_entries) > 0:
            invocation = await self.oracle.functions["publish_data_entries"].invoke(
                new_entries=[{"Future": entry} for entry in serialized_future_entries],
                max_fee=max_fee,
            )
            invocations.append(invocation)
            logger.debug(str(invocation))
            logger.info(
                "Sent %d updated future entries with transaction %s",
                len(serialized_future_entries),
                hex(invocation.hash),
            )

        return invocations

    @deprecated
    async def get_spot_entries(self, pair_id, sources=None) -> List[SpotEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            DataType(DataTypes.SPOT, pair_id, None).serialize(), sources
        )
        entries = response[0]
        return [SpotEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_all_sources(self, data_type: DataType) -> List[str]:
        (response,) = await self.oracle.functions["get_all_sources"].call(
            data_type.serialize()
        )

        return [felt_to_str(source) for source in response]

    @deprecated
    async def get_future_entries(
        self, pair_id, expiration_timestamp, sources=None
    ) -> List[FutureEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            DataType(DataTypes.FUTURE, pair_id, expiration_timestamp).serialize(),
            sources,
        )
        entries = response[0]
        return [FutureEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_spot(
        self,
        pair_id,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ) -> OracleResponse:
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                DataType(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                DataType(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
                sources,
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
        pair_id,
        expiry_timestamp,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ) -> OracleResponse:
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                DataType(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                DataType(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
                sources,
            )

        response = dict(response)

        return OracleResponse(
            response["price"],
            response["decimals"],
            response["last_updated_timestamp"],
            response["num_sources_aggregated"],
            response["expiration_timestamp"],
        )

    async def get_decimals(self, data_type: DataType) -> int:
        (response,) = await self.oracle.functions["get_decimals"].call(
            data_type.serialize()
        )

        return response

    @deprecated
    async def set_checkpoint(
        self,
        pair_id: int,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        max_fee=int(1e18),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.oracle.functions["set_checkpoint"].invoke(
            DataType(DataTypes.SPOT, pair_id, None).serialize(),
            aggregation_mode.serialize(),
            max_fee=max_fee,
        )
        return invocation

    @deprecated
    async def set_future_checkpoint(
        self,
        pair_id: int,
        expiry_timestamp: int,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        max_fee=int(1e18),
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.oracle.functions["set_checkpoint"].invoke(
            DataType(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
            aggregation_mode.serialize(),
            max_fee=max_fee,
        )
        return invocation

    # TODO (#000): Fix future checkpoints
    async def set_future_checkpoints(
        self,
        pair_ids: List[int],
        expiry_timestamps: List[int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        max_fee=int(1e18),
        pagination: Optional[int] = 15,
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = None
        if pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[index : index + pagination]
                invocation = await self.oracle.functions["set_checkpoints"].invoke(
                    pair_ids_subset,
                    expiry_timestamps,
                    aggregation_mode.serialize(),
                    max_fee=max_fee,
                )
                index += pagination
                logger.debug(str(invocation))
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
                max_fee=max_fee,
            )

        return invocation

    async def set_checkpoints(
        self,
        pair_ids: List[int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        max_fee=int(1e18),
        pagination: Optional[int] = 15,
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = None
        if pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[index : index + pagination]
                invocation = await self.oracle.set_checkpoints.invoke(
                    [
                        DataType(DataTypes.SPOT, pair_id, None).serialize()
                        for pair_id in pair_ids_subset
                    ],
                    aggregation_mode.serialize(),
                    max_fee=max_fee,
                )
                index += pagination
                logger.debug(str(invocation))
                logger.info(
                    "Set checkpoints for %d pair IDs with transaction %s",
                    len(pair_ids_subset),
                    hex(invocation.hash),
                )
        else:
            invocation = await self.oracle.set_checkpoints.invoke(
                [
                    DataType(DataTypes.SPOT, pair_id, None).serialize()
                    for pair_id in pair_ids
                ],
                aggregation_mode.serialize(),
                max_fee=max_fee,
            )

        return invocation

    async def get_admin_address(self) -> int:
        (response,) = await self.oracle.functions["get_admin_address"].call()
        return response

    async def update_oracle(
        self,
        implementation_hash: int,
        max_fee=int(1e18),
    ) -> InvokeResult:
        invocation = await self.oracle.functions["upgrade"].invoke(
            implementation_hash,
            max_fee=max_fee,
        )
        return invocation
