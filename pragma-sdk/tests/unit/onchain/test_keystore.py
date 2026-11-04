"""
`keystore:PATH:PASSWORD` keys: eth-keyfile >= 0.9 decodes the password as
bytes and raised AttributeError on the str starknet.py forwards.
"""

import json

from eth_keyfile import create_keyfile_json

from pragma_sdk.onchain.client import PragmaOnChainClient


def test_keystore_with_str_password(tmp_path):
    key = 0x1234ABCD
    path = tmp_path / "keystore.json"
    path.write_text(
        json.dumps(
            create_keyfile_json(key.to_bytes(32, "big"), b"test-password", kdf="scrypt")
        )
    )
    client = PragmaOnChainClient.__new__(PragmaOnChainClient)
    key_pair = client._process_secret_key((str(path), "test-password"))
    assert key_pair.private_key == key
