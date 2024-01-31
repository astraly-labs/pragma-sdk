# pylint: disable=protected-access

import asyncio
from typing import Callable, Optional, Tuple
from warnings import warn

from starknet_py.contract import Contract as StarknetContract
from starknet_py.contract import ContractFunction, InvokeResult
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import Hash, SentTransactionResponse


class Contract(StarknetContract):
    def __getattr__(self, attr):
        if attr in self._functions:
            return self._functions[attr]

        if attr in dir(self):
            return getattr(self, attr)

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

    transaction = await self._account.sign_invoke_v1_transaction(
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
    await invoke_result.wait_for_acceptance()

    return invoke_result


# patch contract function to use new invoke function
ContractFunction.invoke = invoke_
