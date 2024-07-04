Setup a new account
==========

You can do so using `Starkli <https://github.com/xJonathanLEI/starkli>`_:

.. code-block:: bash
    
    starkli signer gen-keypair

Store the given private key somewhere safe you can then use it in the next commands:

.. code-block:: bash

    starkli account oz init /path/to/account.json --private-key <0x..>
    starkli account deploy /path/to/account.json --private-key <0x..>

For more information, check the Starkli Documentation.
