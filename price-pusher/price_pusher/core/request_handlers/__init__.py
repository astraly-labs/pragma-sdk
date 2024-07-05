from typing import Dict

from price_pusher.types import Target

from .api import APIRequestHandler
from .chain import ChainRequestHandler
from .interface import IRequestHandler


REQUEST_HANDLER_REGISTRY: Dict[Target, IRequestHandler] = {
    "onchain": ChainRequestHandler,
    "offchain": APIRequestHandler,
}

__all__ = ["APIRequestHandler", "ChainRequestHandler", "REQUEST_HANDLER_REGISTRY"]
