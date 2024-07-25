from redis import Redis


class RedisManager:
    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store(self, key: str, value: str):
        self.client.set(key, value)

    def get(self, key: str):
        return self.client.get(key)
