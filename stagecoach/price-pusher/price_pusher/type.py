from enum import Enum

UnixTimestamp = int
DurationInSeconds = int


class Envirronment(Enum):
    DEV = 1
    PROD = 2


class DataSource(Enum):
    ONCHAIN = 1
    OFFCHAIN = 2
    DEFILLAMA = 3
