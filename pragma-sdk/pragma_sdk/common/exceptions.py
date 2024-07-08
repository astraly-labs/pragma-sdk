class BasePragmaException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def serialize(self) -> str:
        return self.message

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BasePragmaException):
            return NotImplemented
        return self.message == other.message

    def __repr__(self) -> str:
        return self.message


class PublisherFetchError(BasePragmaException): ...


class UnsupportedAssetError(BasePragmaException): ...


class ClientException(BasePragmaException): ...
