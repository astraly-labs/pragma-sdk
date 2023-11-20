import os

from pragma.core.client import PragmaClient

START_BLOCK = int(os.environ.get("START_BLOCK", 0))
NETWORK = os.environ.get("NETWORK", "testnet")
ADMIN_PRIVATE_KEY = int(os.environ["ADMIN_PRIVATE_KEY"], 0)
ADMIN_CONTRACT_ADDRESS = int(os.environ["ADMIN_CONTRACT_ADDRESS"], 0)
VRF_CONTRACT_ADDRESS = int(os.environ["VRF_CONTRACT_ADDRESS"], 16)

def handler(event, context):

    client = PragmaClient(network=NETWORK, account_private_key=ADMIN_PRIVATE_KEY, account_contract_address=ADMIN_CONTRACT_ADDRESS)
    await client.init_randomness_contract(VRF_CONTRACT_ADDRESS)

    await client.handle_random(ADMIN_PRIVATE_KEY, START_BLOCK)

    return {
        "success": True,
    }