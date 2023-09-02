import asyncio
from typing import Callable, Optional, Tuple

from starknet_py.contract import Contract as StarknetContract
from starknet_py.contract import ContractFunction, InvokeResult
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import (
    Hash,
    SentTransactionResponse,
    TransactionExecutionStatus,
    TransactionFinalityStatus,
    TransactionReceipt,
    TransactionStatus,
)
from starknet_py.transaction_errors import (
    TransactionFailedError,
    TransactionNotReceivedError,
    TransactionRejectedError,
    TransactionRevertedError,
)


class Contract(StarknetContract):
    def __getattr__(self, attr):
        if attr in self._functions:
            return self._functions[attr]
        elif attr in dir(self):
            return getattr(self, attr)
        else:
            raise AttributeError("Invalid Attribute")


async def invoke_(
    self,
    *args,
    max_fee: Optional[int] = None,
    auto_estimate: bool = False,
    callback: Optional[Callable[[SentTransactionResponse], None]] = None,
    **kwargs,
) -> InvokeResult:
    """
    Allows for a callback in the invocation of a contract method.
    This is useful for tracking the nonce changes
    """
    prepared_call = self.prepare(*args, **kwargs)

    # transfer ownership to the prepared call
    self = prepared_call
    if max_fee is not None:
        self.max_fee = max_fee

    transaction = await self._account.sign_invoke_transaction(
        calls=self,
        max_fee=self.max_fee,
        auto_estimate=auto_estimate,
    )
    response = await self._client.send_transaction(transaction)

    if callback:
        await callback(transaction.nonce, response.transaction_hash)

    invoke_result = InvokeResult(
        hash=response.transaction_hash,
        _client=self._client,
        contract=self._contract_data,
        invoke_transaction=transaction,
    )

    # don't return invoke result until it is received or errors
    await wait_for_received(self._client, invoke_result.hash)

    return invoke_result


# https://community.starknet.io/t/efficient-utilization-of-sequencer-capacity-in-starknet-v0-12-1/95607
async def wait_for_received(
    self,
    tx_hash: Hash,
    wait_for_accept: Optional[bool] = None,  # pylint: disable=unused-argument
    check_interval: float = 2,
    retries: int = 500,
) -> TransactionReceipt:
    # pylint: disable=too-many-branches
    """
    Awaits for transaction to get accepted or at least pending by polling its status.

    :param tx_hash: Transaction's hash.
    :param wait_for_accept:
        .. deprecated:: 0.17.0
            Parameter `wait_for_accept` has been deprecated - since Starknet 0.12.0, transactions in a PENDING
            block have status ACCEPTED_ON_L2.
    :param check_interval: Defines interval between checks.
    :param retries: Defines how many times the transaction is checked until an error is thrown.
    :return: Transaction receipt.
    """
    if check_interval <= 0:
        raise ValueError("Argument check_interval has to be greater than 0.")
    if retries <= 0:
        raise ValueError("Argument retries has to be greater than 0.")
    if wait_for_accept is not None:
        warnings.warn(
            "Parameter `wait_for_accept` has been deprecated - since Starknet 0.12.0, transactions in a PENDING"
            " block have status ACCEPTED_ON_L2."
        )

    while True:
        try:
            tx_receipt = await self.get_transaction_receipt(tx_hash=tx_hash)

            deprecated_status = _status_to_finality_execution(tx_receipt.status)
            finality_status = tx_receipt.finality_status or deprecated_status[0]
            execution_status = tx_receipt.execution_status or deprecated_status[1]

            if execution_status == TransactionExecutionStatus.REJECTED:
                raise TransactionRejectedError(message=tx_receipt.rejection_reason)

            if execution_status == TransactionExecutionStatus.REVERTED:
                raise TransactionRevertedError(message=tx_receipt.revert_error)

            if execution_status == TransactionExecutionStatus.SUCCEEDED:
                return tx_receipt

            if finality_status in (
                TransactionFinalityStatus.ACCEPTED_ON_L2,
                TransactionFinalityStatus.ACCEPTED_ON_L1,
            ):
                return tx_receipt

            retries -= 1
            if retries == 0:
                raise TransactionNotReceivedError()

            await asyncio.sleep(check_interval)

        except asyncio.CancelledError as exc:
            raise TransactionNotReceivedError from exc
        except ClientError as exc:
            if "Transaction hash not found" not in exc.message:
                raise exc
            retries -= 1
            if retries == 0:
                raise TransactionNotReceivedError from exc

            await asyncio.sleep(check_interval)


def _status_to_finality_execution(
    status: Optional[TransactionStatus],
) -> Tuple[Optional[TransactionFinalityStatus], Optional[TransactionExecutionStatus]]:
    if status is None:
        return None, None
    finality_statuses = [finality.value for finality in TransactionFinalityStatus]
    if status.value in finality_statuses:
        return TransactionFinalityStatus(status.value), None
    return None, TransactionExecutionStatus(status.value)


# patch contract function to use new invoke function
ContractFunction.invoke = invoke_
