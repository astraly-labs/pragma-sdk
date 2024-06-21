import click
import logging
import re
from .config import read_price_config_file

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@click.command()
@click.option('--config-file', help='Path to config.yaml')
@click.option('--log-level', default='INFO', help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
@click.option('--network', help='<onchain|offchain:testnet|mainnet>')
@click.option('--private-key', help='<aws|keystore:secret_name|path>')
@click.option('--publisher-name', help='Your publisher name')
@click.option('--publisher-address', help='Your publisher address')
@click.option('--api-key', default=None, help='pragma api key to publish offchain')
def main(log_level, config_file, network, private_key, publisher_name, publisher_address, api_key):
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)
    
    config = read_price_config_file(config_file)
    print(config)
    
    if network and not re.match(r'^(onchain|offchain):(testnet|mainnet)$',network):
        raise click.BadParameter("Network must be in the format <onchain|offchain:testnet|mainnet>")
    # run


if __name__ == "__main__":
    main()
