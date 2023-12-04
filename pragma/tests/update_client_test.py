import time
from typing import Tuple
from urllib.parse import urlparse
import aiohttp
import json
import logging
import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account
from starknet_py.net.client_errors import ClientError
from pragma.core.client import PragmaClient
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.core.types import ContractAddresses, DataType, DataTypes
from pragma.core.utils import str_to_felt
from pragma.tests.constants import CURRENCIES, PAIRS, FORK_BLOCK_NUMBER
from pragma.tests.utils import read_contract
from pragma.tests.utils import get_declarations, get_deployments
from starknet_py.transaction_errors import TransactionRevertedError

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
MAX_FEE = 3700000000000000
PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = str_to_felt("ETH/USD")
BTC_PAIR = str_to_felt("BTC/USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"




@pytest_asyncio.fixture(scope="package")
async def declare_oracle(
    pragma_fork_client: PragmaClient
) -> DeclareResult:
    try:
        compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
        compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)
        # Declare Oracle
        declare_result = await Contract.declare(
            account=pragma_fork_client.account,
            compiled_contract=compiled_contract,
            compiled_contract_casm=compiled_contract_casm,
            auto_estimate=True,
        )
        await declare_result.wait_for_acceptance()
        return declare_result

    except ClientError as e:
        if e.code == -32603: 
            logger.info(f"Contract already declared with this class hash")
        else: 
            logger.info(f"An error occured during the declaration: {e}")
        return None


@pytest_asyncio.fixture(scope="package", name="pragma_fork_client")
async def pragma_fork_client(
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    deployments = get_deployments()
    oracle = deployments["pragma_Oracle"]
    registry = deployments["pragma_PublisherRegistry"]
    address, private_key = address_and_private_key
    # Parse port from network url
    port = urlparse(network).port
    return PragmaClient(
        network="fork_devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(registry["address"], oracle["address"]),
        port=port,
    )



@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_update_oracle(pragma_fork_client: PragmaClient, network, declare_oracle: DeclareResult) : 
    if declare_oracle is None:
        pytest.skip("oracle_declare failed. Skipping this test...")


    # Set up initial configuration

    publisher_name = "PRAGMA"
    publisher_address = pragma_fork_client.account_address()

    await pragma_fork_client.add_publisher(publisher_name, publisher_address)

    # Add PRAGMA as Source for PRAGMA Publisher
    await pragma_fork_client.add_source_for_publisher(publisher_name, SOURCE_1)

    # Publish SPOT Entry
    timestamp = int(time.time())
    await pragma_fork_client.publish_spot_entry(
        BTC_PAIR, 100, timestamp, SOURCE_1, publisher_name, volume=int(200 * 100 * 1e8)
    )
    await pragma_fork_client.publish_spot_entry(
        ETH_PAIR, 100, timestamp, SOURCE_1, publisher_name, volume=int(200 * 100 * 1e8)
    )
    # Publish FUTURE Entry
    expiry_timestamp = timestamp + 1000
    future_entry_1 = FutureEntry(
        BTC_PAIR,
        1000,
        timestamp,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=10000,
    )
    future_entry_2 = FutureEntry(
        ETH_PAIR,
        2000,
        timestamp + 100,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=20000,
    )

    await pragma_fork_client.publish_many([future_entry_1, future_entry_2])
    # Retrieve old state
    publishers = await pragma_fork_client.get_all_publishers()
    eth_spot_price = await pragma_fork_client.get_spot(ETH_PAIR)
    eth_future_price = await pragma_fork_client.get_future(ETH_PAIR, expiry_timestamp)
    btc_spot_price = await pragma_fork_client.get_spot(BTC_PAIR)
    btc_future_price = await pragma_fork_client.get_future(BTC_PAIR, expiry_timestamp)
    oracle_admin = await pragma_fork_client.get_admin_address()
    assert oracle_admin == pragma_fork_client.account_address()
    # Determine new implementation hash 
    declare_result = declare_oracle
    logger.info(f"Contract declared with hash: {declare_result.class_hash}")
    # Update oracle
    update_invoke = await pragma_fork_client.update_oracle(declare_result.class_hash, MAX_FEE)
    logger.info(f"Contract upgraded with tx  {hex(update_invoke.hash)}")
    # Check that the class hash was updated
    class_hash_json = await check_class_hash_rpc(network)
    class_hash = json.loads(class_hash_json)
    # assert class_hash['result'] == declare_result.class_hash
    assert int(class_hash['result'],16) == declare_result.class_hash
    # Retrieve new state
    new_publishers = await pragma_fork_client.get_all_publishers()
    new_eth_spot_price = await pragma_fork_client.get_spot(ETH_PAIR)
    new_eth_future_price = await pragma_fork_client.get_future(ETH_PAIR, expiry_timestamp)
    new_btc_spot_price = await pragma_fork_client.get_spot(BTC_PAIR)
    new_btc_future_price = await pragma_fork_client.get_future(BTC_PAIR, expiry_timestamp)

    # Check that state is the same
    assert publishers == new_publishers
    assert eth_spot_price.price == new_eth_spot_price.price
    assert eth_spot_price.last_updated_timestamp == new_eth_spot_price.last_updated_timestamp
    assert eth_spot_price.decimals == new_eth_spot_price.decimals
    assert eth_spot_price.num_sources_aggregated  == new_eth_spot_price.num_sources_aggregated
    assert eth_future_price.price == new_eth_future_price.price
    assert eth_future_price.last_updated_timestamp == new_eth_future_price.last_updated_timestamp
    assert eth_future_price.decimals == new_eth_future_price.decimals
    assert eth_future_price.num_sources_aggregated  == new_eth_future_price.num_sources_aggregated
    assert btc_spot_price.price == new_btc_spot_price.price 
    assert btc_spot_price.last_updated_timestamp == new_btc_spot_price.last_updated_timestamp
    assert btc_spot_price.decimals == new_btc_spot_price.decimals
    assert btc_spot_price.num_sources_aggregated  == new_btc_spot_price.num_sources_aggregated
    assert btc_future_price.price == new_btc_future_price.price
    assert btc_future_price.last_updated_timestamp == new_btc_future_price.last_updated_timestamp
    assert btc_future_price.decimals == new_btc_future_price.decimals
    assert btc_future_price.num_sources_aggregated  == new_btc_future_price.num_sources_aggregated


async def check_class_hash_rpc(network): 
    # Check that the class hash was updated
    deployments = get_deployments()
    oracle_address = deployments['pragma_Oracle']['address']
    url = f"{network}"
    payload = {
        "jsonrpc": "2.0",
        "method": "starknet_getClassHashAt",
        "params": [
            "latest",
            f"{oracle_address}"
        ],
        "id": 1
    }
    headers = {'Content-Type': 'application/json'}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=json.dumps(payload)) as response:
            response_text = await response.text()
            return(response_text)

