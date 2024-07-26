from typing import Optional, Dict, Tuple, Union


from pragma_sdk.common.types.types import DataTypes, UnixTimestamp
from pragma_sdk.common.utils import str_to_felt


class Asset:
    data_type: DataTypes
    asset_id: int
    expiration_timestamp: Optional[UnixTimestamp]

    def __init__(
        self,
        data_type: DataTypes,
        asset_id: str | int,
        expiration_timestamp: Optional[UnixTimestamp] = None,
    ):
        if isinstance(asset_id, str):
            asset_id = str_to_felt(asset_id)
        elif not isinstance(asset_id, int):
            raise TypeError(
                "Asset ID must be string (will be converted to felt) or integer"
            )

        self.asset_id = asset_id
        self.data_type = data_type
        self.expiration_timestamp = expiration_timestamp

    def serialize(self) -> Dict[str, Union[int | Tuple[int, Optional[int]]]]:
        """
        Serialize method used to interact with Cairo contracts.
        """
        match self.data_type:
            case DataTypes.SPOT:
                return {"SpotEntry": self.asset_id}
            case DataTypes.FUTURE:
                return {"FutureEntry": (self.asset_id, self.expiration_timestamp)}
            case DataTypes.GENERIC:
                return {"GenericEntry": self.asset_id}

    def to_dict(self) -> Dict[str, Union[int, str, None]]:
        key_name = (
            "pair_id" if self.data_type in [DataTypes.SPOT, DataTypes.FUTURE] else "key"
        )
        return {
            key_name: self.asset_id,
            "data_type": self.data_type.name,
            "expiration_timestamp": self.expiration_timestamp,
        }
