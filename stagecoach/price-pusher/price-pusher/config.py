from typing import List
from .types import PriceConfig, PriceConfigFile
import yaml

def read_price_config_file(path: str) -> List[PriceConfig]:
    with open(path, 'r') as file:
        price_configs = yaml.safe_load(file)
    
    price_config_file = PriceConfigFile(root=price_configs)
    
    return price_config_file.root