from starknet_py.utils.merkle_tree import MerkleTree


def serialize_merkle_tree(merkle_tree: MerkleTree) -> dict:
    return {
        "leaves": merkle_tree.leaves,
        "hash_method": merkle_tree.hash_method.name.upper(),
        "root_hash": hex(merkle_tree.root_hash),
        "levels": merkle_tree.levels,
    }
