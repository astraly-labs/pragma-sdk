import click
import logging
from .config import read_price_config_file

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@click.command()
@click.option('--config-file', help='Path to config.yaml')
@click.option('--log-level', default='INFO', help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
def main(log_level, config_file):
    # CLI
    # Parse argv
    # get log level
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)
    
    # retrieve config from file

    config = read_price_config_file(config_file)
    print(config)

    # run


if __name__ == "__main__":
    main()
