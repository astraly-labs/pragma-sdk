import logging
from sys import stdout

logger = logging.getLogger(__name__)


def get_stream_logger():
    global logger

    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    stream_handler.setFormatter(formatter)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(stream_handler)

    return logger
