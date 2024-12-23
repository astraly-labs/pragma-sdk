import logging
from logging import Logger
from sys import stdout


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

    # Configure formatting
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s:%(name)s.%(module)s:%(message)s"
    )

    # Configure handlers
    for handler in logger.handlers:
        handler.setFormatter(formatter)
        handler.setLevel(numeric_log_level)

    # If no handlers exist, add a stream handler
    if not logger.handlers:
        stream_handler = logging.StreamHandler(stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(numeric_log_level)
        logger.addHandler(stream_handler)

    # Set logger and root logger levels
    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)
