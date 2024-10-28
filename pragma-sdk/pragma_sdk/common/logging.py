import logging
from sys import stdout
from typing import Optional


class PragmaLogger:
    _instance: Optional[logging.Logger] = None

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """
        Return the singleton logger instance with a stream handler.
        Log format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        The logger level is set to DEBUG.
        Ensures only one stream handler exists.
        """
        if cls._instance is None:
            # Create logger instance
            logger = logging.getLogger("pragma_sdk")
            logger.propagate = False
            logger.setLevel(logging.DEBUG)

            # Check if handler already exists
            if not logger.handlers:
                stream_handler = logging.StreamHandler(stdout)
                formatter = logging.Formatter(
                    "[%(asctime)s] %(levelname)s:%(name)s.%(module)s:%(message)s"
                )
                stream_handler.setFormatter(formatter)
                logger.addHandler(stream_handler)

            cls._instance = logger

        return cls._instance


def get_pragma_sdk_logger() -> logging.Logger:
    """
    Convenience function to get the pragma sdk logger.
    """
    return PragmaLogger.get_logger()
