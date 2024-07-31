import asyncio
from typing import Dict, Literal, Optional

from starknet_py.net.client import Client
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import TransactionStatus
from starknet_py.transaction_errors import TransactionNotReceivedError


class NonceMixin:
    client: Client
    account_contract_address: Optional[int]
    nonce_status: Dict[int, TransactionStatus] = {}
    nonce_dict: Dict[int, int] = {}
    pending_nonce: Optional[int] = None

    async def _get_nonce(self) -> int:
        """
        Returns the nonce that should be used for the next transaction.
        Steps:
        1. Update nonces' statuses.
        2. Cleanup nonce_dict.
        3. Return the pending nonce if there is one.
        4. Return the latest nonce if there are no pending nonces.
        """
        await self.update_nonce_dict()
        self.cleanup_nonce_dict()

        if self.pending_nonce:
            return self.pending_nonce
        if self.nonce_status:
            return max(self.nonce_status) + 1

        latest_nonce = await self.get_nonce()
        return latest_nonce

    def cleanup_nonce_dict(self):
        """
        Cleanup the nonce_dict by removing all txs that have been either rejected or accepted.
        """

        nonce_seq = [
            x
            for x in self.nonce_dict
            if self.nonce_status[x]
            in [
                TransactionStatus.ACCEPTED_ON_L1,
                TransactionStatus.ACCEPTED_ON_L2,
                TransactionStatus.REJECTED,
            ]
        ]
        if nonce_seq:
            max_accepted = max(nonce_seq)
            for nonce in list(self.nonce_dict):
                if nonce <= max_accepted:
                    del self.nonce_dict[nonce]
                    if nonce in self.nonce_status:
                        del self.nonce_status[nonce]
            if self.pending_nonce and self.pending_nonce < max_accepted:
                self.pending_nonce = None

    async def track_nonce(
        self,
        nonce: int,
        transaction_hash: int,
    ) -> None:
        """
        Callback function to track the nonce of a transaction.
        Will update the nonce_dict and pending_nonce attributes.
        We track the nonce used for a given transaction hash.

        :param nonce: The nonce of the transaction.
        :param transaction_hash: The hash of the transaction.
        """

        self.nonce_dict[nonce] = transaction_hash

        nonce_min = min(self.nonce_dict)
        nonce_max = max(self.nonce_dict)
        for i in range(nonce_min, nonce_max + 1):
            if i not in self.nonce_dict:
                self.pending_nonce = i
                break

    async def update_nonce_dict(
        self,
    ):
        """
        Update the statuses of the nonces in the nonce_dict.
        """
        for nonce in list(self.nonce_dict):
            self.nonce_status[nonce] = await self.get_status(self.nonce_dict[nonce])
            if self.nonce_status[nonce] in [
                TransactionStatus.REJECTED,
            ]:
                # assume all later transaction will fail because this nonce was skipped
                self.pending_nonce = nonce
                self.nonce_dict = {}
                self.nonce_status = {}
                return

    async def get_nonce(
        self,
        include_pending=True,
        block_number: Optional[int | str | Literal["pending", "latest"]] = None,
    ) -> int:
        """
        Get the nonce of the account contract address.
        Just a wrapper around the client's get_contract_nonce method.

        :param include_pending: Whether to include pending transactions in the nonce calculation.
        :param block_number: Custom block number to get the nonce from.
        """
        if not block_number:
            block_number = "pending" if include_pending else "latest"

        nonce = await self.client.get_contract_nonce(
            self.account_contract_address,
            block_number=block_number,
        )

        return nonce  # type: ignore[no-any-return]

    async def get_status(
        self,
        transaction_hash: int,
        check_interval: int = 2,
        retries: int = 500,
    ) -> TransactionStatus:
        """
        Tries to get the status of a transaction by its hash.

        :param transaction_hash: The hash of the transaction.
        :param check_interval: The interval in seconds between each check.
        :param retries: The number of retries before giving up.
        :return: The status of the transaction.
        """
        if check_interval <= 0:
            raise ValueError("Argument check_interval has to be greater than 0.")
        if retries <= 0:
            raise ValueError("Argument retries has to be greater than 0.")

        while True:
            retries -= 1
            try:
                tx_status = await self.client.get_transaction_status(
                    tx_hash=transaction_hash
                )

                return tx_status.finality_status

            except asyncio.CancelledError as exc:
                raise TransactionNotReceivedError from exc
            except ClientError as exc:
                if "Transaction hash not found" not in exc.message:
                    raise exc

                await asyncio.sleep(check_interval)
