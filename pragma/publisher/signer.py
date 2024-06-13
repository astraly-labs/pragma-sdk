import collections
from typing import List

from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner
from starknet_py.utils.typed_data import TypedData

from pragma.core.entry import SpotEntry

GetDataResponse = collections.namedtuple(
    "GetDataResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)


def build_publish_message(entries: List[SpotEntry]) -> TypedData:
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
            "entries": SpotEntry.serialize_entries(entries),
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

    return message


class OffchainSigner:
    def __init__(self, signer: StarkCurveSigner):
        self.signer = signer

    def sign_publish_message(
        self, entries: List[SpotEntry]
    ) -> (List[int], int):  # type: ignore
        """
        Sign a publish message

        :param entries: List of SpotEntry objects
        :return: Tuple containing the signature and the message hash
        """
        message = build_publish_message(entries)
        hash_ = TypedData.from_dict(message).message_hash(self.account.address)
        sig = self.signer.sign_message(message)

        return sig, hash_
