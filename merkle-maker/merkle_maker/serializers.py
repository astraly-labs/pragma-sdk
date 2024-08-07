from starknet_py.utils.merkle_tree import MerkleTree


def serialize_merkle_tree(merkle_tree: MerkleTree) -> dict:
    serialized_levels = [list(map(hex, level)) for level in merkle_tree.levels]
    return {
        "leaves": list(map(hex, merkle_tree.leaves)),
        "hash_method": merkle_tree.hash_method.name.upper(),
        "root_hash": hex(merkle_tree.root_hash),
        "levels": serialized_levels,
    }
