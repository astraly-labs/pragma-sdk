import asyncio
import json
import os
import boto3

from pragma.core.client import PragmaClient

START_BLOCK = int(os.environ.get("START_BLOCK", 0))
NETWORK = os.environ.get("NETWORK", "sepolia")
SECRET_NAME = os.environ["SECRET_NAME"]
ADMIN_CONTRACT_ADDRESS = int(os.environ["ADMIN_CONTRACT_ADDRESS"], 16)
VRF_CONTRACT_ADDRESS = int(os.environ["VRF_CONTRACT_ADDRESS"], 16)


def handler(event, context):
    asyncio.run(main())

    return {
        "success": True,
    }


def _get_pvt_key():
    region_name = "eu-west-3"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
    return int(
        json.loads(get_secret_value_response["SecretString"])["ADMIN_PRIVATE_KEY"],
        16,
    )


async def main():
    admin_private_key = _get_pvt_key()

    client = PragmaClient(
        network=NETWORK,
        account_private_key=admin_private_key,
        account_contract_address=ADMIN_CONTRACT_ADDRESS,
    )
    client.init_randomness_contract(VRF_CONTRACT_ADDRESS)

    await client.handle_random(admin_private_key, START_BLOCK)


if __name__ == "__main__":
    asyncio.run(main())
