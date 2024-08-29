import asyncio


class ThreadSafeQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.lock = asyncio.Lock()

    async def put(self, item):
        async with self.lock:
            await self.queue.put(item)

    async def get(self):
        async with self.lock:
            return await self.queue.get()

    def empty(self):
        return self.queue.empty()
