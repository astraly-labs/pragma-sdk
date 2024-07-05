import asyncio
import logging

from typing import Callable, Optional, TypeVar, Any, Awaitable

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def retry_async(
    action: Callable[[], Awaitable[T]],
    retries: int,
    delay_in_s: int,
) -> Optional[Any]:
    """
    Retries an asynchronous action every `delay` seconds up to `retries` times.

    Args:
        action: The asynchronous action to retry.
        retries: The maximum number of retries.
        delay: The delay in seconds between retries.

    Returns:
        The result of the action if successful, None if all retries failed.
    """
    for attempt in range(retries):
        try:
            logger.info("🙏 Retry successfull!")
            return await action()
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay_in_s)
            else:
                raise Exception(f"Action failed after {retries} attempts: {e}")
    return None
