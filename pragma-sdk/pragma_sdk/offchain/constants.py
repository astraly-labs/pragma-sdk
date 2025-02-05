from pragma_sdk.common.types.types import Environment
from typing import Dict

PRAGMA_API_URLS: Dict[Environment, str] = {
    Environment.DEV: "https://api.dev.pragma.build",
    Environment.PROD: "https://api.prod.pragma.build",
}

WEBSOCKET_TIME_TO_EXPIRE = 60 * 60  # 1 hour
