from typing import Dict, Literal

from .api import APIRequestHandler
from .chain import ChainRequestHandler
from .interface import IRequestHandler

ALLOWED_TARGETS = Literal["onchain", "offchain"]

REQUEST_HANDLER_REGISTRY: Dict[ALLOWED_TARGETS, IRequestHandler] = {
    "onchain": ChainRequestHandler,
    "offchain": APIRequestHandler,
}

__all__ = ["APIRequestHandler", "ChainRequestHandler", "REQUEST_HANDLER_REGISTRY"]
