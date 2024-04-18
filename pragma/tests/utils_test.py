import pytest

from pragma.publisher.fetchers.index import IndexAggregation
from pragma.tests.constants import SAMPLE_ASSET_QUANTITIES, SAMPLE_SPOT_ENTRIES
from pragma.tests.fetcher_configs import INDEX_CONFIGS


@pytest.fixture
def sample_spot_entries():
    return SAMPLE_SPOT_ENTRIES


@pytest.fixture(params=INDEX_CONFIGS.values())
def index_fetcher_config(request):
    return request.param


def test_get_index_value(
    index_fetcher_config,
    sample_spot_entries,
):
    # Create an instance of IndexAggregation
    for i in range(len(SAMPLE_ASSET_QUANTITIES)):
        index_aggregation = IndexAggregation(
            sample_spot_entries, SAMPLE_ASSET_QUANTITIES[i]
        )
        expected_index_value = index_fetcher_config["expected_result"][i]
        # Calculate the index value
        index_value = index_aggregation.get_index_value()

        # Assert that the calculated index value matches the expected value
        assert index_value == expected_index_value.price  # Adjust rounding as needed
