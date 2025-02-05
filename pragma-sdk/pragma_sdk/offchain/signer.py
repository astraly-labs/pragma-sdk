from typing import List, Optional, Tuple

from starknet_py.net.signer.stark_curve_signer import StarkCurveSigner
from starknet_py.utils.typed_data import TypedData

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import DataTypes


def build_publish_message(
    entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
) -> TypedData:
    """
    Builds a typed data message to publish spot entries on the Pragma API.
    see https://community.starknet.io/t/snip-off-chain-signatures-a-la-eip712 for reference

    :param entries: List of SpotEntry objects
    :return: The typed data message
    """

    message = {
        "domain": {"name": "Pragma", "version": "1", "chainId": "1", "revision": "1"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": Entry.serialize_entries(entries),
        },
        "types": {
            "StarknetDomain": [
                {"name": "name", "type": "shortstring"},
                {"name": "version", "type": "shortstring"},
                {"name": "chainId", "type": "shortstring"},
                {"name": "revision", "type": "shortstring"},
            ],
            "Request": [
                {"name": "action", "type": "shortstring"},
                {"name": "entries", "type": "Entry*"},
            ],
            "Entry": [
                {"name": "base", "type": "Base"},
                {"name": "pair_id", "type": "shortstring"},
                {"name": "price", "type": "u128"},
                {"name": "volume", "type": "u128"},
            ],
            "Base": [
                {"name": "publisher", "type": "shortstring"},
                {"name": "source", "type": "shortstring"},
                {"name": "timestamp", "type": "timestamp"},
            ],
        },
    }
    if data_type == DataTypes.FUTURE:
        message["types"]["Entry"] += [  # type: ignore[index]
            {"name": "expiration_timestamp", "type": "timestamp"},
        ]

    return TypedData.from_dict(message)


def build_login_message(publisher_name: str, expiration_timestamp: int) -> TypedData:
    """
    Builds a typed data message to login to the Pragma API.

    :param publisher_name: The account address to login
    :return: The typed data message
    """
    message = {
        "domain": {"name": "Pragma", "version": "1", "chainId": "1", "revision": "1"},
        "primaryType": "Request",
        "message": {
            "publisher_name": publisher_name,
            "expiration_timestamp": expiration_timestamp,
        },
        "types": {
            "StarknetDomain": [
                {"name": "name", "type": "shortstring"},
                {"name": "version", "type": "shortstring"},
                {"name": "chainId", "type": "shortstring"},
                {"name": "revision", "type": "shortstring"},
            ],
            "Request": [
                {"name": "publisher_name", "type": "shortstring"},
                {"name": "expiration_timestamp", "type": "timestamp"},
            ],
        },
    }
    return TypedData.from_dict(message)


class OffchainSigner:
    """
    Class used to sign messages for the Pragma API
    """

    def __init__(self, signer: StarkCurveSigner):
        self.signer = signer

    def sign_publish_message(
        self, entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
    ) -> Tuple[List[int], int]:
        """
        Sign a publish message

        :param entries: List of SpotEntry objects
        :return: Tuple containing the signature and the message hash
        """
        message = build_publish_message(entries, data_type)
        hash_ = message.message_hash(self.signer.address)
        sig = self.signer.sign_message(message, self.signer.address)
        return sig, hash_

    def sign_login_message(
        self, publisher_name: str, expiration_timestamp: int
    ) -> Tuple[List[int], int]:
        """
        Sign a login message

        :param publisher_name: The publisher name to login
        :return: Tuple containing the signature and the message hash
        """
        message = build_login_message(publisher_name, expiration_timestamp)
        hash_ = message.message_hash(self.signer.address)
        sig = self.signer.sign_message(message, self.signer.address)
        return sig, hash_
