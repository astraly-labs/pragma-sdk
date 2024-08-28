import asyncio

from typing import Dict, List

from testcontainers.core.waiting_utils import wait_for_logs
from starknet_py.net.full_node_client import FullNodeClient

from vrf_listener.main import main as vrf_listener

from benchmark.devnet import starknet_devnet_container, DEVNET_PORT
from benchmark.accounts import get_users_client, get_admin_account
from benchmark.deploy import deploy_randomness_contracts
from benchmark.stresstest import process_user, RequestInfo


def spawn_vrf_listener(
    vrf_address: int,
    admin_address: int,
    private_key: str,
) -> asyncio.Task:
    """
    Spawns the main function in a parallel thread and return the task.
    The task can later be cancelled using the .cancel function.
    """
    vrf_listener_task = asyncio.create_task(
        vrf_listener(
            network="devnet",
            rpc_url=f"http://127.0.0.1:{DEVNET_PORT}",
            vrf_address=hex(vrf_address),
            admin_address=admin_address,
            private_key=private_key,
            check_requests_interval=1,
        )
    )
    return vrf_listener_task


async def main():
    with starknet_devnet_container() as devnet:
        # 0. run devnet
        print("🧩 Starting devnet...")
        wait_for_logs(devnet, "Starknet Devnet listening")
        print("✅ done!")

        full_node = FullNodeClient(node_url=f"http://127.0.0.1:{DEVNET_PORT}")

        # 1. deploy vrf etc etc
        print("🧩 Deploying VRF contracts...")
        (deployer, deployer_info) = get_admin_account(full_node)
        randomness_contracts = await deploy_randomness_contracts(deployer)
        print("✅ done!")

        # 2. create accounts that will submit requests
        print("🧩 Deploying VRF contracts...")
        users = await get_users_client(randomness_contracts)
        print(f"Got {len(users)} that will spam requests...")

        # 3. starts VRF listener
        print("🧩 Spawning the VRF listener...")
        vrf_listener = spawn_vrf_listener(
            vrf_address=randomness_contracts[0].address,
            admin_address=deployer_info.account_address,
            private_key=deployer_info.private_key,
        )
        # TODO: is it possible to create "wait_for_ready" for the vrf_listener?
        await asyncio.sleep(10)
        print("✅ done!")

        # 5. send txs requests
        print("🧩 Starting VRF request spam...")
        num_requests_per_user = 5
        all_request_infos: Dict[str, List[RequestInfo]] = {}

        async def process_all_users():
            tasks = []
            for user in users:
                task = asyncio.create_task(
                    process_user(user, randomness_contracts[1], num_requests_per_user)
                )
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            for user, request_infos in zip(users, results):
                all_request_infos[user.account.address] = request_infos

        await process_all_users()

        # 6. kill the vrf task
        vrf_listener.cancel()

        # 7. Stats
        print("✅ VRF request spam completed!")

        total_requests = sum(len(infos) for infos in all_request_infos.values())
        total_fulfillment_time = sum(
            (info.fulfillment_time - info.request_time).total_seconds()
            for infos in all_request_infos.values()
            for info in infos
            if info.fulfillment_time
        )
        avg_fulfillment_time = total_fulfillment_time / total_requests

        print(f"Total requests: {total_requests}")
        print(f"Average fulfillment time: {avg_fulfillment_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
