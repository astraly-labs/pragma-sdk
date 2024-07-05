import logging
from logging import Logger
from sys import stdout

logger = logging.getLogger(__name__)


def get_stream_logger() -> Logger:
    """
    Return the logger with a stream handler.
    Log format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    The logger level is set to DEBUG.
    There can only be one stream handler.
    """

    global logger

    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler.setFormatter(formatter)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(stream_handler)

    return logger


def setup_logging(logger: Logger, log_level: str) -> None:
    """
    Set up the logging configuration based on the provided log level.

    Args:
        logger: The logger to update
        log_level: The logging level to set (e.g., "DEBUG", "INFO").
    """
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if numeric_log_level is None:
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(level=numeric_log_level)
    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)
