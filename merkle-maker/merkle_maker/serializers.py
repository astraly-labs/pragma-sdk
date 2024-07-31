from starknet_py.utils.merkle_tree import MerkleTree


def merkle_tree_to_dict(merkle_tree: MerkleTree) -> dict:
    return {
        "leaves": merkle_tree.leaves,
        "hash_method": merkle_tree.hash_method.name.upper(),
        "root_hash": merkle_tree.root_hash,
        "levels": merkle_tree.levels,
    }
