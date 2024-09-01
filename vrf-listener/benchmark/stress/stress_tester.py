import asyncio

from typing import List, Literal, Optional, Dict
from statistics import median
from pydantic import HttpUrl
from testcontainers.core.waiting_utils import wait_for_logs

from starknet_py.net.account.account import Account
from starknet_py.contract import Contract
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair

from pragma_sdk.onchain.abis.abi import get_erc20_abi
from vrf_listener.main import main as vrf_listener

from benchmark.client import ExtendedPragmaClient
from benchmark.config.accounts_config import AccountConfig, AccountsConfig
from benchmark.deploy import deploy_randomness_contracts
from benchmark.devnet.container import starknet_devnet_container
from benchmark.stress.txs_spam import spam_reqs_with_user, RequestInfo
from benchmark.constants import FEE_TOKEN_ADDRESS


class StressTester:
    oracle_address: Optional[int]
    config: AccountsConfig

    network: Literal["devnet", "mainnet", "sepolia"]
    rpc_url: Optional[HttpUrl] = None

    txs_per_user: int

    def __init__(
        self,
        network: Literal["devnet", "mainnet", "sepolia"],
        rpc_url: HttpUrl,
        accounts_config: AccountsConfig,
        txs_per_user: int,
        oracle_address: Optional[str],
    ) -> None:
        self.network = network
        self.rpc_url = rpc_url
        self.config = accounts_config
        self.txs_per_user = txs_per_user
        self.oracle_address = int(oracle_address, 16) if oracle_address else None

    async def run_stresstest(self) -> None:
        full_node = FullNodeClient(node_url=self.rpc_url)

        # 1. Deploy vrf etc etc
        print("\n🧩 Deploying VRF contracts...")
        (deployer, deployer_info) = self.config.get_admin_account(full_node, self.network)
        randomness_contracts = await deploy_randomness_contracts(
            network=self.network,
            deployer=deployer,
            oracle_address=self.oracle_address,
        )
        print("✅ done!")

        # 2. Using the admin account,
        print("\n🫅 Admin sending ETH to all users...")
        all_users_infos = self.config.get_users_accounts_configs()
        await self._fund_users_using_admin(deployer, all_users_infos)
        print("✅ done!")

        # 3. create accounts that will submit requests
        print("\n🧩 Creating user clients...")
        users = await self.config.get_users_client(
            network=self.network,
            rpc_url=self.rpc_url,
            randomness_contracts=randomness_contracts,
        )
        print("✅ done!")
        print(f"👀 Got {len(users)} users that will spam requests")

        # 4. starts VRF listener
        print("\n🧩 Spawning the VRF listener...")
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
        print("\n🧩 Starting VRF request spam...")
        all_request_infos = await self.spam_txs_with_users(
            users=users,
            vrf_example_contract=randomness_contracts[1],
        )
        print("✅ spam requests done! 🥳")

        # 6. kill the vrf task
        print("\n⏳ Stopping the VRF listener...")
        await asyncio.sleep(5)
        vrf_listener.cancel()

        # 7. Show & Save Stats
        print("\n🤓 Computed Statistics:")
        self.compute_and_show_stats(all_request_infos=all_request_infos)
        self.save_statistics(all_request_infos=all_request_infos)

        # 8. Send remaining balance of users to admin
        print("\n🙏 Users are now refunding the admin... thanks!")
        await self._refund_admin_with_users(
            client=full_node,
            users=all_users_infos,
            admin=deployer,
        )
        print("✅ done!")

    async def run_devnet_stresstest(self) -> None:
        """
        Full end-to-end stresstest for the devnet.
        """
        # 0. Start the devnet
        with starknet_devnet_container() as devnet:
            wait_for_logs(devnet, "Starknet Devnet listening")

            full_node = FullNodeClient(node_url=self.rpc_url)

            # 1. deploy vrf etc etc
            print("\n🧩 Deploying VRF contracts...")
            (deployer, deployer_info) = self.config.get_admin_account(full_node, self.network)
            randomness_contracts = await deploy_randomness_contracts(
                network=self.network,
                deployer=deployer,
            )
            print("✅ done!")

            # 2. create accounts that will submit requests
            print("\n🧩 Creating user clients...")
            users = await self.config.get_users_client(
                network=self.network,
                rpc_url=self.rpc_url,
                randomness_contracts=randomness_contracts,
            )
            print(f"👀 Got {len(users)} users that will spam requests")

            # 3. starts VRF listener
            print("\n🧩 Spawning the VRF listener...")
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
            print("\n🧩 Starting VRF request spam...")
            all_request_infos = await self.spam_txs_with_users(
                users=users,
                vrf_example_contract=randomness_contracts[1],
            )
            print("✅ spam requests done! 🥳")

            # 6. kill the vrf task
            print("\n⏳ Stopping the VRF listener...")
            await asyncio.sleep(5)
            vrf_listener.cancel()

            # 8. Show & Save Stats
            print("\n🤓 Computed Statistics:")
            self.compute_and_show_stats(all_request_infos=all_request_infos)
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
                network=self.network,
                rpc_url=self.rpc_url if self.rpc_url else None,
                vrf_address=hex(vrf_address),
                admin_address=admin_address,
                private_key=private_key,
                check_requests_interval=1,
                ignore_request_threshold=5,
            )
        )
        return vrf_listener_task

    async def spam_txs_with_users(
        self,
        users: List[ExtendedPragmaClient],
        vrf_example_contract: Contract,
    ) -> Dict[str, List[RequestInfo]]:
        """
        Takes a list of users and spams TXs using the example contract.
        """
        all_request_infos: Dict[str, List[RequestInfo]] = {}

        tasks = []
        for user in users:
            task = asyncio.create_task(
                spam_reqs_with_user(
                    user=user,
                    example_contract=vrf_example_contract,
                    txs_per_user=self.txs_per_user,
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Let all tasks the time to rly finish
        await asyncio.sleep(5)

        for user, request_infos in zip(users, results):
            all_request_infos[user.account.address] = request_infos

        return all_request_infos

    def compute_and_show_stats(
        self,
        all_request_infos: Dict[str, List[RequestInfo]],
    ) -> None:
        """
        Given the result of the spam - computes and prints info.
        """
        total_requests = sum(len(infos) for infos in all_request_infos.values())
        fulfillment_times = [
            info.fulfillment_time - info.request_time
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
        TODO: Save stats for CI stuff
        """
        pass

    async def _fund_users_using_admin(self, admin: Account, users: List[AccountConfig]) -> None:
        """
        Using the admin account of the Accounts configuration, sends 0.1 eth
        to each account present in the list of users.
        If the admin has not enough balance, the benchmark fails.

        0.3 ETH = 300000000000000000
        """
        eth_contract = Contract(
            address=FEE_TOKEN_ADDRESS,
            abi=get_erc20_abi(),
            provider=admin,
            cairo_version=0,
        )

        (admin_balance,) = await eth_contract.functions["balanceOf"].call(
            admin.address,
            block_hash="pending",
        )
        minimum_balance_accepted = (300000000000000000 * len(users)) + 300000000000000000
        if minimum_balance_accepted > admin_balance:
            raise ValueError(f"😹🫵 Admin is too poor. Need at least {minimum_balance_accepted}")

        # Sends 0.1 eth to each user
        for user in users:
            invoke = await eth_contract.functions["transfer"].invoke_v1(
                int(user.account_address, 16),
                300000000000000000,
                auto_estimate=True,
            )
            await invoke.wait_for_acceptance(check_interval=2)
            await asyncio.sleep(2)

    async def _refund_admin_with_users(
        self, client: FullNodeClient, users: List[AccountConfig], admin: Account
    ) -> None:
        """
        Using all the users, check their balance & send everything to the admin.
        """
        chain = StarknetChainId.SEPOLIA if self.network == "sepolia" else StarknetChainId.MAINNET

        for user_cfg in users:
            user_account = Account(
                address=user_cfg.account_address,
                client=client,
                key_pair=KeyPair.from_private_key(int(user_cfg.private_key, 16)),
                chain=chain,
            )
            eth_contract = Contract(
                address=FEE_TOKEN_ADDRESS,
                abi=get_erc20_abi(),
                provider=user_account,
                cairo_version=0,
            )
            (user_balance,) = await eth_contract.functions["balanceOf"].call(
                user_account.address,
                block_hash="pending",
            )

            prepared_call = eth_contract.functions["transfer"].prepare_invoke_v1(
                admin.address,
                user_balance,
            )
            estimate_fee = await prepared_call.estimate_fee()
            user_balance_after_fees = user_balance - (estimate_fee.overall_fee + 10)

            tx = await eth_contract.functions["transfer"].invoke_v1(
                admin.address, user_balance_after_fees, auto_estimate=True
            )
            await tx.wait_for_acceptance()
