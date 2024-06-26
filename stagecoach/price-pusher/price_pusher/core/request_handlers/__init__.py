from typing import Dict

from .api import APIRequestHandler
from .chain import ChainRequestHandler
from .interface import IRequestHandler

REQUEST_HANDLER_REGISTRY: Dict[str, IRequestHandler] = {
    "onchain": ChainRequestHandler,
    "offchain": APIRequestHandler,
}

__all__ = ["APIRequestHandler", "ChainRequestHandler", "REQUEST_HANDLER_REGISTRY"]
