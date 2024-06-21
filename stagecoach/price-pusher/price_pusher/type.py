from enum import Enum


class Envirronment(Enum):
    DEV = 1
    PROD = 2


class DataSource(Enum):
    ONCHAIN = 1
    OFFCHAIN = 2
    DEFILLAMA = 3


UnixTimestamp = int
DurationInSeconds = int
