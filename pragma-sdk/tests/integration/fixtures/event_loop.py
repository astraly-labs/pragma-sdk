# This fixture was added to enable using async fixtures
import asyncio
import pytest_asyncio


@pytest_asyncio.fixture(scope="module")
async def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
