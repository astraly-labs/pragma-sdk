import os

from pragma.randomness import handle_random

START_BLOCK = int(os.environ.get("START_BLOCK", 0))

def handler(event, context):
    handle_random(START_BLOCK, "/cli-config.ini")
    return {
        "success": True,
    }