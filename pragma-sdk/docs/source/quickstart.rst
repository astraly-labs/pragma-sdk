Quickstart
==========

This is a quickstart guide to get you up and running with the Pragma SDK.

Fetch data
---------------

To fetch data on 3rd parties API, one can use the `FetcherClient <pragma_sdk.common.fetchers>`.

Here is step by step example:

``` python

```

.. hint::

    If you are experiencing transaction failures with ``FEE_TRANSFER_FAILURE``
    make sure that the address you are trying to deploy is prefunded with enough
    tokens, and verify that ``max_fee`` argument in :meth:`~starknet_py.net.account.account.Account.sign_deploy_account_v1`
    or ``l1_resource_bounds`` argument in :meth:`~starknet_py.net.account.account.Account.sign_deploy_account_v3` is set
    to a high enough value.
