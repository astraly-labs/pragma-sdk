import asyncio
import os

from pragma.core.client import PragmaClient

START_BLOCK = int(os.environ.get("START_BLOCK", 0))
NETWORK = os.environ.get("NETWORK", "sepolia")
ADMIN_PRIVATE_KEY = int(os.environ["ADMIN_PRIVATE_KEY"], 16)
ADMIN_CONTRACT_ADDRESS = int(os.environ["ADMIN_CONTRACT_ADDRESS"], 16)
VRF_CONTRACT_ADDRESS = int(os.environ["VRF_CONTRACT_ADDRESS"], 16)


def handler(event, context):
    asyncio.run(main())

    return {
        "success": True,
    }


async def main():
    client = PragmaClient(
        network=NETWORK,
        account_private_key=ADMIN_PRIVATE_KEY,
        account_contract_address=ADMIN_CONTRACT_ADDRESS,
    )
    client.init_randomness_contract(VRF_CONTRACT_ADDRESS)

    await client.handle_random(ADMIN_PRIVATE_KEY, START_BLOCK)


if __name__ == "__main__":
    asyncio.run(main())
