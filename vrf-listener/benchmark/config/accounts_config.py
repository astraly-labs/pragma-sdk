import yaml

from typing import List, Optional, Literal
from pydantic import BaseModel, validator, HttpUrl
from pathlib import Path

from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.models import StarknetChainId
from starknet_py.contract import Contract

from benchmark.client import ExtendedPragmaClient, create_pragma_client


class AccountConfig(BaseModel):
    account_address: str
    private_key: str
    is_admin: Optional[bool] = False


class AccountsConfig(BaseModel):
    accounts: List[AccountConfig]

    @validator("accounts")
    def validate_single_admin(cls, accounts):
        admin_count = sum(1 for account in accounts if account.is_admin)
        if admin_count != 1:
            raise ValueError(f"⛔ There must be exactly one admin account. Found {admin_count}.")
        return accounts

    @classmethod
    def from_yaml(cls, path: Path) -> "AccountsConfig":
        with open(path, "r") as file:
            accounts_data = yaml.safe_load(file)
        return cls(accounts=[AccountConfig(**account) for account in accounts_data])

    def get_admin_account_config(self) -> AccountConfig:
        return [account for account in self.accounts if account.is_admin][0]

    def get_users_accounts_configs(self) -> List[AccountConfig]:
        return [account for account in self.accounts if not account.is_admin]

    def get_account_config_by_address(self, address: str) -> Optional[AccountConfig]:
        for account in self.accounts:
            if account.account_address == address:
                return account
        return None

    def get_admin_account(
        self,
        client: FullNodeClient,
        network: Literal["devnet", "mainnet", "sepolia"],
    ) -> (Account, AccountConfig):
        admin_cfg = self.get_admin_account_config()
        chain = StarknetChainId.SEPOLIA if network == "sepolia" else StarknetChainId.MAINNET
        return (
            Account(
                address=admin_cfg.account_address,
                client=client,
                key_pair=KeyPair.from_private_key(int(admin_cfg.private_key, 16)),
                chain=chain,
            ),
            admin_cfg,
        )

    async def get_admin_client(
        self,
        network: Literal["devnet", "mainnet", "sepolia"],
        rpc_url: HttpUrl,
        randomness_contracts: (Contract, Contract, Contract),
    ) -> ExtendedPragmaClient:
        admin_cfg = self.get_admin_account_config()
        await create_pragma_client(
            network=network,
            rpc_url=rpc_url,
            randomness_contracts=randomness_contracts,
            account_address=admin_cfg.account_address,
            private_key=admin_cfg.private_key,
        )

    async def get_users_client(
        self,
        network: Literal["devnet", "mainnet", "sepolia"],
        rpc_url: HttpUrl,
        randomness_contracts: (Contract, Contract, Contract),
    ) -> List[ExtendedPragmaClient]:
        users_cfg = self.get_users_accounts_configs()
        return [
            await create_pragma_client(
                network=network,
                rpc_url=rpc_url,
                randomness_contracts=randomness_contracts,
                account_address=user_cfg.account_address,
                private_key=user_cfg.private_key,
            )
            for user_cfg in users_cfg
            if not user_cfg.is_admin
        ]


DEVNET_PREDEPLOYED_ACCOUNTS: List[AccountConfig] = [
    # This is the admin account (deployer etc...)
    AccountConfig(
        account_address="0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201",
        private_key="0x00000000000000000000000000000000c10662b7b247c7cecf7e8a30726cff12",
        is_admin=True,
    ),
    # All users
    AccountConfig(
        account_address="0x14923a0e03ec4f7484f600eab5ecf3e4eacba20ffd92d517b213193ea991502",
        private_key="0x00000000000000000000000000000000e5852452e0757e16b127975024ade3eb",
    ),
    AccountConfig(
        account_address="0x18f81c2ef42310e0abd4fafd27f37beb34d000641beb2cd8a6fb97596552ddb",
        private_key="0x0000000000000000000000000000000016b0be70a6344cccf3ed6e7d9cf04de4",
    ),
    AccountConfig(
        account_address="0x57424c05ff19a6ecd48c96fe15eef472f51623b14cac5649d18f23463bcee78",
        private_key="0x000000000000000000000000000000002b34b214e9fdffe665f24862df66ebb9",
    ),
    AccountConfig(
        account_address="0x79ef5d5437a6592150a058b75da25676975a360604138d44d81953574a0bb5d",
        private_key="0x000000000000000000000000000000008f79b17298e62ff2cf07d4373839dcf4",
    ),
    AccountConfig(
        account_address="0x6805c245473baaaf463e8077b2852a5533bcdf430583732daba61f7bfcb0dc",
        private_key="0x00000000000000000000000000000000cc31749edc490700c6f649618fd7bc7f",
    ),
    AccountConfig(
        account_address="0x2ba23586e58db94b7412a80a4267d39553e5ab4aac9a5f8d9b6123759fda9b3",
        private_key="0x000000000000000000000000000000005dacb7e735abeb109226fe97691a3d19",
    ),
    AccountConfig(
        account_address="0x38bd66246efa3d2d2d98380d1900c502d2fbe972446b9540f3a45022408351b",
        private_key="0x00000000000000000000000000000000e02fbe3d9d4ebc9e47c791bb8a406e96",
    ),
    AccountConfig(
        account_address="0x73c911eb568b6c82199d6335d5f01027e78a2b4089ed4604d4d1852388a438a",
        private_key="0x00000000000000000000000000000000c3f32713d5f755d670b913d3acf9c4b4",
    ),
    AccountConfig(
        account_address="0x6a41708a2379d0328ff6797007a1e4d85ca934d69fa64c4e465d3a99a167fb5",
        private_key="0x00000000000000000000000000000000dc76d257c6cfd7833e92380910a81f93",
    ),
]

DEVNET_PREDEPLOYED_ACCOUNTS_CONFIG = AccountsConfig(accounts=DEVNET_PREDEPLOYED_ACCOUNTS)
