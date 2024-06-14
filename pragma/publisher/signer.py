from typing import List, Optional

from starknet_py.net.signer.stark_curve_signer import StarkCurveSigner
from starknet_py.utils.typed_data import TypedData

from pragma.core.entry import Entry
from pragma.core.types import DataTypes


def build_publish_message(
    entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
) -> TypedData:
    """
    Builds a typed data message to publish spot entries on the Pragma API.
    see https://community.starknet.io/t/snip-off-chain-signatures-a-la-eip712 for reference

    :param entries: List of SpotEntry objects
    """

    message = {
        "domain": {"name": "Pragma", "version": "1"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": Entry.serialize_entries(entries),
        },
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Request": [
                {"name": "action", "type": "felt"},
                {"name": "entries", "type": "Entry*"},
            ],
            "Entry": [
                {"name": "base", "type": "Base"},
                {"name": "pair_id", "type": "felt"},
                {"name": "price", "type": "felt"},
                {"name": "volume", "type": "felt"},
            ],
            "Base": [
                {"name": "publisher", "type": "felt"},
                {"name": "source", "type": "felt"},
                {"name": "timestamp", "type": "felt"},
            ],
        },
    }
    if data_type == DataTypes.FUTURE:
        message["types"]["Entry"] = message["types"]["Entry"] + [
            {"name": "expiration_timestamp", "type": "felt"},
        ]

    return TypedData.from_dict(message)


class OffchainSigner:
    def __init__(self, signer: StarkCurveSigner):
        self.signer = signer

    def sign_publish_message(
        self, entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
    ) -> (List[int], int):  # type: ignore
        """
        Sign a publish message

        :param entries: List of SpotEntry objects
        :return: Tuple containing the signature and the message hash
        """
        message = build_publish_message(entries, data_type)
        hash_ = message.message_hash(self.signer.address)
        sig = self.signer.sign_message(message, self.signer.address)
        return sig, hash_
