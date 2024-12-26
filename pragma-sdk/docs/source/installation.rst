Installation
============

To use pragma-sdk, ``ecdsa, fastecdsa, sympy`` dependencies are required. Depending on the operating system,
different installation steps must be performed.

We highly recommend using `uv <https://docs.astral.sh/uv/>`_ to manage your project dependencies.

Linux
-----

.. code-block:: bash

    sudo apt install -y libgmp3-dev
    pip install pragma-sdk
    # or
    uv add pragma-sdk

MacOS
-----

Instructions assume `Homebrew <https://brew.sh/>`_ being installed.

.. hint:: If you are experiencing issues installing pragma-sdk related to ``fastecdsa`` on recent versions of MacOS
    consider installing ``cmake`` with version ``>=3.22.4``.

    .. code-block:: bash

        brew install cmake

    It is required to build `crypto-cpp-py <https://github.com/software-mansion-labs/crypto-cpp-py>`_
    dependency in case it hasn't been updated to support newest MacOS versions.

Intel processor
^^^^^^^^^^^^^^^

.. code-block:: bash

    brew install gmp
    pip install pragma-sdk

Apple silicon
^^^^^^^^^^^^^

.. code-block:: bash

    brew install gmp
    CFLAGS=-I`brew --prefix gmp`/include LDFLAGS=-L`brew --prefix gmp`/lib pip install pragma-sdk

Windows
-------

You can install pragma-sdk on Windows in two ways:

1. Install it just like you would on Linux.

In such case make sure that you have `MinGW <https://www.mingw-w64.org/>`_ installed and up-to-date.

.. hint::
    The recommended way to install is through `chocolatey <https://community.chocolatey.org/packages/mingw>`_.

    You also should have MinGW in your PATH environment variable (e.g. ``C:\ProgramData\chocolatey\lib\mingw\tools\install\mingw64\bin``).

.. warning::
    Please be aware that you may encounter issues related to ``libcrypto_c_exports`` (e.g LoadLibraryEx).
    Installing MinGW via chocolatey and correctly adding it to the PATH should solve these issues.

If you encounter any further problems related to installation, you can create an `issue at our GitHub <https://github.com/software-mansion/pragma-sdk/issues/new?assignees=&labels=bug&projects=&template=bug_report.yaml&title=%5BBUG%5D+%3Ctitle%3E>`_
or ask for help in `Pragma Telegram Channel <https://t.me/+Xri-uUMpWXI3ZmRk>`_.

2. Use virtual machine with Linux, `Windows Subsystem for Linux 2 <https://learn.microsoft.com/en-us/windows/wsl/>`_ (WSL2).
