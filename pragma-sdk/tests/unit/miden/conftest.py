"""
Local conftest for Miden unit tests.
Overrides the root conftest to avoid loading integration fixtures
that depend on optional modules (pragma_sdk.offchain, devnet, etc.).
"""

collect_ignore_glob = []
