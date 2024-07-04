# This is needed for importing fixtures from `fixtures` directory
pytest_plugins = [
    "tests.integration.fixtures.event_loop",
    "tests.integration.fixtures.accounts",
    "tests.integration.fixtures.misc",
    "tests.integration.fixtures.devnet",
    "tests.integration.fixtures.clients",
    "tests.integration.fixtures.fetchers",
    "tests.integration.client_test",
    "tests.integration.update_client_test",
]
