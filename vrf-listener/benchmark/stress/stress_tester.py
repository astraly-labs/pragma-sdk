import asyncio

from typing import List, Literal, Optional, Dict
from statistics import median
from pydantic import HttpUrl
from testcontainers.core.waiting_utils import wait_for_logs
from starknet_py.contract import Contract
from starknet_py.net.full_node_client import FullNodeClient

from vrf_listener.main import main as vrf_listener

from benchmark.client import ExtendedPragmaClient
from benchmark.config.accounts_config import AccountsConfig
from benchmark.devnet.deploy import deploy_randomness_contracts
from benchmark.devnet.container import starknet_devnet_container
from benchmark.stress.txs_spam import spam_reqs_with_user, RequestInfo


class StressTester:
    vrf_address: str
    config: AccountsConfig

    network: Literal["devnet", "mainnet", "sepolia"]
    rpc_url: Optional[HttpUrl] = None

    txs_per_user: int

    def __init__(
        self,
        network: Literal["devnet", "mainnet", "sepolia"],
        vrf_address: str,
        accounts_config: AccountsConfig,
        txs_per_user: int,
        rpc_url: Optional[HttpUrl] = None,
    ) -> None:
        self.network = network
        self.vrf_address = vrf_address
        self.config = accounts_config
        self.rpc_url = rpc_url
        self.txs_per_user = txs_per_user

    async def run_stresstest(self) -> None:
        raise NotImplementedError("TODO: sepolia/mainnet test")

    async def run_devnet_stresstest(self) -> None:
        # 0. Start the devnet
        with starknet_devnet_container() as devnet:
            wait_for_logs(devnet, "Starknet Devnet listening")

            full_node = FullNodeClient(node_url=self.rpc_url)

            # 1. deploy vrf etc etc
            print("🧩 Deploying VRF contracts...")
            (deployer, deployer_info) = self.config.get_admin_account(full_node, self.network)
            randomness_contracts = await deploy_randomness_contracts(deployer)
            print("✅ done!")

            # 2. create accounts that will submit requests
            print("🧩 Creating user clients...")
            users = await self.config.get_users_client(randomness_contracts)
            print(f"Got {len(users)} users that will spam requests 👀")

            # 3. starts VRF listener
            print("🧩 Spawning the VRF listener...")
            vrf_listener = self.spawn_vrf_listener(
                vrf_address=randomness_contracts[0].address,
                admin_address=deployer_info.account_address,
                private_key=deployer_info.private_key,
            )
            # TODO: is it possible to create "wait_for_ready" for the vrf_listener?
            print("⏳ waiting a bit to be sure the task is spawned...")
            await asyncio.sleep(5)
            print("✅ done!")

            # 5. send txs requests
            print("🧩 Starting VRF request spam...")
            all_request_infos = await self.spam_txs_with_users(
                users=users,
                vrf_example_contract=randomness_contracts[1],
            )
            print("✅ spam requests done! 🥳")

            # 6. kill the vrf task
            print("⏳ Stopping the VRF listener...")
            await asyncio.sleep(5)
            vrf_listener.cancel()

            # 7. Show Stats
            self.compute_and_show_stats(all_request_infos=all_request_infos)

            # 8. TODO: Save stats for CI stuff
            self.save_statistics(all_request_infos=all_request_infos)

    def spawn_vrf_listener(
        self,
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
                rpc_url=self.rpc_url if self.rpc_url else None,
                vrf_address=hex(vrf_address),
                admin_address=admin_address,
                private_key=private_key,
                check_requests_interval=1,
                ignore_request_threshold=10,
            )
        )
        return vrf_listener_task

    async def spam_txs_with_users(
        self,
        users: List[ExtendedPragmaClient],
        vrf_example_contract: Contract,
    ) -> Dict[str, List[RequestInfo]]:
        all_request_infos: Dict[str, List[RequestInfo]] = {}

        tasks = []
        for user in users:
            task = asyncio.create_task(
                spam_reqs_with_user(
                    user=user,
                    example_contract=vrf_example_contract,
                    num_requests=self.txs_per_user,
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        for user, request_infos in zip(users, results):
            all_request_infos[user.account.address] = request_infos

        return all_request_infos

    def compute_and_show_stats(
        self,
        all_request_infos: Dict[str, List[RequestInfo]],
    ) -> None:
        print("🤓 Computed Statistics:")
        total_requests = sum(len(infos) for infos in all_request_infos.values())
        fulfillment_times = [
            (info.fulfillment_time - info.request_time).total_seconds()
            for infos in all_request_infos.values()
            for info in infos
            if info.fulfillment_time
        ]
        avg_fulfillment_time = sum(fulfillment_times) / total_requests
        median_fulfillment_time = median(fulfillment_times)
        print(f"Total requests: {total_requests}")
        print(f"Average fulfillment time: {avg_fulfillment_time:.2f} seconds")
        print(f"Median fulfillment time: {median_fulfillment_time:.2f} seconds")

    def save_statistics(
        self,
        all_request_infos: Dict[str, List[RequestInfo]],
    ) -> None:
        """
        TODO.
        """
        pass
