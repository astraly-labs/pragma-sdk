import collections

OracleResponse = collections.namedtuple(
    "OracleResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)
