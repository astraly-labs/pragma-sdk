import asyncio
import os
import sys

import typer
from dotenv import load_dotenv
from pymongo import MongoClient

from pragma.core.randomness.randomness_utils import ecvrf_verify
from pragma.core.types import get_client_from_network

load_dotenv()


async def verify_random(transaction_hash: str, network):
    """provide the hex transaction number to verify the proof for that transaction.  If no event is found will alert the user"""
    client = MongoClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DATABASE_NAME")]
    collection = db[os.getenv("COLLECTION_NAME")]
    document = collection.find_one({"tx_hash": transaction_hash})
    if document is None:
        typer.echo("No event found")
        return
    pub_key = b"V\xf9\x10\xb2\x15\xd9\xedM\x12\xc6\x06\x1d\rZ\xf4!\x04?\x04B\x8d\xb7f\xa5_\xe8\xec;\xe6\xbe\x98\xb6"
    client = get_client_from_network(network)
    print(int(document["minimum_block_number"]))
    block = await client.get_block(block_number=int(document["minimum_block_number"]))
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
