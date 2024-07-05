from typing import Optional, Dict, Tuple, Union


from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.utils import str_to_felt


class Asset:
    data_type: DataTypes
    pair_id: int
    expiration_timestamp: Optional[int]

    def __init__(
        self,
        data_type: DataTypes,
        pair_id: str | int,
        expiration_timestamp: Optional[int],
    ):
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        self.pair_id = pair_id
        self.data_type = data_type
        self.expiration_timestamp = expiration_timestamp

    def serialize(self) -> Dict[str, Union[int | Tuple[int, Optional[int]]]]:
        """
        Serialize method used to interact with Cairo contracts.
        """
        if self.data_type == DataTypes.SPOT:
            return {"SpotEntry": self.pair_id}
        if self.data_type == DataTypes.FUTURE:
            return {"FutureEntry": (self.pair_id, self.expiration_timestamp)}
        return {}

    def to_dict(self) -> Dict[str, Union[int, str, None]]:
        return {
            "pair_id": self.pair_id,
            "expiration_timestamp": self.expiration_timestamp,
            "data_type": self.data_type.name,
        }
