import logging
from logging import Logger


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
