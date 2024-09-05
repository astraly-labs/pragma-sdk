import asyncio

from typing import Awaitable, Callable, Optional, Any, Dict, List

from starknet_py.net.account.account import Call
from starknet_py.contract import Contract as StarknetContract
from starknet_py.contract import ContractFunction, InvokeResult
from starknet_py.net.client_models import SentTransactionResponse

from pragma_sdk.onchain.types.execution_config import ExecutionConfig


class Contract(StarknetContract):  # type: ignore[misc]
    def __getattr__(self, attr: str) -> Any:
        if attr in self._functions:
            return self._functions[attr]

        if attr in dir(self):
            return getattr(self, attr)

        raise AttributeError("Invalid Attribute")


# Global dictionary to store locks for each account
account_locks: Dict[str, asyncio.Lock] = {}


async def _multicall(
    self: Contract,
    prepared_calls: List[Call],
    execution_config: ExecutionConfig = ExecutionConfig(auto_estimate=True),
    callback: Optional[
        Callable[[SentTransactionResponse, str], Awaitable[None]]
    ] = None,
) -> InvokeResult:
    """
    Allows for a callback in the invocation of a contract method.
    This is useful for tracking the nonce changes
    """
    # Get or create a lock for this account
    account_address = str(self.account.address)
    if account_address not in account_locks:
        account_locks[account_address] = asyncio.Lock()

    # We have concurrency issues on the account if we don't do this
    # because two calls parallel can end up generating the same nonce.
    # We really want to avoid that.
    async with account_locks[account_address]:
        transaction = (
            await self.account.sign_invoke_v3(
                calls=prepared_calls,
                l1_resource_bounds=execution_config.l1_resource_bounds,
                auto_estimate=execution_config.auto_estimate,
            )
            if execution_config.enable_strk_fees
            else await self.account.sign_invoke_v1(
                calls=prepared_calls,
                max_fee=execution_config.max_fee,
            )
        )

    response = await self.client.send_transaction(transaction)
    if callback:
        await callback(transaction.nonce, response.transaction_hash)

    invoke_result = InvokeResult(
        hash=response.transaction_hash,
        _client=self.client,
        contract=self,
        invoke_transaction=transaction,
    )

    return invoke_result


async def _invoke(
    self: Contract,
    *args: Any,
    execution_config: ExecutionConfig = ExecutionConfig(auto_estimate=True),
    callback: Optional[
        Callable[[SentTransactionResponse, str], Awaitable[None]]
    ] = None,
    **kwargs: Any,
) -> InvokeResult:
    """
    Allows for a callback in the invocation of a contract method.
    This is useful for tracking the nonce changes
    """

    prepared_call = (
        self.prepare_invoke_v3(*args, **kwargs)
        if execution_config.enable_strk_fees
        else self.prepare_invoke_v1(*args, **kwargs)
    )

    # transfer ownership to the prepared call
    self = prepared_call
    if execution_config.max_fee is not None:
        self.max_fee = execution_config.max_fee

    # Get or create a lock for this account
    account_address = str(self.get_account.address)
    if account_address not in account_locks:
        account_locks[account_address] = asyncio.Lock()

    # We have concurrency issues on the account if we don't do this
    # because two calls parallel can end up generating the same nonce.
    # We really want to avoid that.
    async with account_locks[account_address]:
        transaction = (
            await self.get_account.sign_invoke_v3(
                calls=self,
                l1_resource_bounds=execution_config.l1_resource_bounds,
                auto_estimate=execution_config.auto_estimate,
            )
            if execution_config.enable_strk_fees
            else await self.get_account.sign_invoke_v1(
                calls=self, max_fee=execution_config.max_fee
            )
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

    return invoke_result


# patch [Contract] with new call
Contract.multicall = _multicall

# patch [ContractFunction] to use new invoke function
ContractFunction.invoke = _invoke
