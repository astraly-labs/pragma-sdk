import sys
from pragma.core.randomness.randomness_utils import ecvrf_verify
import typer
import os 
from pymongo import MongoClient
from dotenv import load_dotenv
from pragma.core.types import get_client_from_network
import asyncio
from starknet_py.hash.utils import private_to_stark_key

load_dotenv()

async def verify_random(transaction_hash: str, network: str = "testnet"):
    """provide the hex transaction number to verify the proof for that transaction.  If no event is found will alert the user"""
    client = MongoClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DATABASE_NAME")]
    collection = db[os.getenv("COLLECTION_NAME")]
    document = collection.find_one({"tx_hash": transaction_hash})
    if document is None:
        typer.echo("No event found")
        return
#     document = {
#         "seed": "1", 
#         "request_id": "0", 
#         "requestor_address": "0x71659c6e691800b9f0d700ea5a96f0dd8f8c5bcf13d91c045853b3699cc7d45", 
#         "minimum_block_number": "7179", 
#         "random_words":["0xbfe57f5490601b776fc51b1411e36b4a7474357ba925ba557157ddd232f08c"], 
#         "proof": [
#   "0x312aabef143e0964791b00468f4b51880ee60739d0318fb895147e79b4d4b8",
#   "0x6b70a8f97e160e26bb3789b2ca012bce8197b7363295c802b0d325043dd7e6",
#   "1368031123306129668851785916954961471260"
# ]

    # }
    pub_key=b'V\xf9\x10\xb2\x15\xd9\xedM\x12\xc6\x06\x1d\rZ\xf4!\x04?\x04B\x8d\xb7f\xa5_\xe8\xec;\xe6\xbe\x98\xb6'
    client = get_client_from_network(network)
    print(int(document["minimum_block_number"]))
    block= await client.get_block(block_number=int(document["minimum_block_number"]))
    block_hash = block.block_hash
    seed = int(document["seed"])
    request_id = int(document["request_id"])
    requestor_address = int(document["requestor_address"], 16)
    seed = (
        request_id.to_bytes(8, sys.byteorder)
        + block_hash.to_bytes(32, sys.byteorder)
        + seed.to_bytes(32, sys.byteorder)
        + requestor_address.to_bytes(32, sys.byteorder)
    )
    print(seed)
    proof_ = document["proof"]
    p0 = int(proof_[0], 16).to_bytes(31, sys.byteorder)
    p1 = int(proof_[1], 16).to_bytes(31, sys.byteorder)
    p2 = int(proof_[2]).to_bytes(18, sys.byteorder)
    _proof = p0 + p1 + p2
    status, val = ecvrf_verify(pub_key, _proof, seed)
    random_word = int(document["random_words"][0], 16)

    typer.echo(f"status: {status}")
    typer.echo(f"verified random value: {int.from_bytes(val, sys.byteorder)}")
    typer.echo(f"onchain random value:  {random_word}")

