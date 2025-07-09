import pytest
import asyncio


# Configure event loop policy
@pytest.fixture(scope="session")
def event_loop_policy():
    """Create and configure event loop policy."""
    return asyncio.get_event_loop_policy()


# This is needed for importing fixtures from `fixtures` directory
pytest_plugins = [
    "tests.integration.fixtures.base",
    "tests.integration.fixtures.accounts",
    "tests.integration.fixtures.misc",
    "tests.integration.fixtures.devnet",
    "tests.integration.fixtures.clients",
    "tests.integration.fixtures.fetchers",
]
