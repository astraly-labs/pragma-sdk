class BasePragmaException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def serialize(self):
        return self.message

    def __eq__(self, other):
        return self.message == other.message

    def __repr__(self):
        return self.message


class PublisherFetchError(BasePragmaException): ...


class UnsupportedAssetError(BasePragmaException): ...


class ClientException(BasePragmaException): ...
