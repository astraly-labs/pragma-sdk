import asyncio
import os
import sys

import requests
import typer
from dotenv import load_dotenv

from pragma.core.randomness.randomness_utils import ecvrf_verify
from pragma.core.types import get_client_from_network

load_dotenv()


async def verify_random(transaction_hash: str, network):
    """provide the hex transaction number to verify the proof for that transaction.  If no event is found will alert the user"""
    document = event_query(transaction_hash)
    pub_key =b'\x8e\x90[b\xe8\x92\x88\x06\xd2S\xcf\xc0\x17\xbf=/qr\x83\x18M\xef1\xc8\x18_\x1c\xc7\xfa\\\x13'
    client = get_client_from_network(network)
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
    p2 = int(proof_[2],16).to_bytes(18, sys.byteorder)
    _proof = p0 + p1 + p2
    status, val = ecvrf_verify(pub_key, _proof, seed)
    random_word = int(document["random_words"][0], 16)

    typer.echo(f"status: {status}")
    typer.echo(f"verified random value: {int.from_bytes(val, sys.byteorder)}")
    typer.echo(f"onchain random value:  {random_word}")




def event_query(contract_hash: str):
    # Define the GraphQL endpoint URL
    graphql_url = 'https://starknet-mainnet-gql.dipdup.net/v1/graphql'

    graphql_query = r"""
    query GetExecutionTrace($contractHash: bytea!) {
    internal_tx(
        where: {hash: {_eq: $contractHash}, entrypoint: {_eq: "submit_random"}}
        order_by: {id: asc}
    ) {
        parsed_calldata
        parsed_result
        entrypoint
        caller {
        hash
        }
        call_type
        contract {
        hash
        }
        calldata
    }
    }
    """

   
    variables = {'contractHash': contract_hash.replace("0x", r"\x")}

    # Define the request payload
    payload = {'query': graphql_query, 'variables': variables}


    # Make the HTTP POST request
    response = requests.post(graphql_url, json=payload)
    proof_index = int(response.json()["data"]["internal_tx"][0]["calldata"][9], 16)
    proof = [response.json()["data"]["internal_tx"][0]["calldata"][i] for i in range(10,10 + proof_index)]
    random_word_index = int(response.json()["data"]["internal_tx"][0]["calldata"][7], 16)
    random_words = [response.json()["data"]["internal_tx"][0]["calldata"][i] for i in range(8,8 + random_word_index)]
    # Print the response content
    return {
        "minimum_block_number": int(response.json()["data"]["internal_tx"][0]["calldata"][3], 16),
        "request_id": int(response.json()["data"]["internal_tx"][0]["calldata"][0],16),
        "seed": int(response.json()["data"]["internal_tx"][0]["calldata"][2],16),
        "requestor_address": response.json()["data"]["internal_tx"][0]["calldata"][1],
        "proof": proof,
        "random_words": random_words,
    }
