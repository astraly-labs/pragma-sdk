# This is needed for importing fixtures from `fixtures` directory
pytest_plugins = [
    "pragma.tests.fixtures.event_loop",
    "pragma.tests.fixtures.accounts",
    "pragma.tests.fixtures.misc",
    "pragma.tests.fixtures.devnet",
    "pragma.tests.fixtures.contracts",
    "pragma.tests.fixtures.clients",
    "pragma.tests.fixtures.fetchers",
    "pragma.tests.client_test",
    "pragma.tests.update_client_test",
]
