from typing import List, Any
from starknet_py.utils.merkle_tree import MerkleTree as StarknetPyMT


MerkleProof = List[int]


class MerkleTree(StarknetPyMT):
    def get_proof(self, target: Any) -> MerkleProof:
        """Generate a Merkle proof for the given target."""
        if not isinstance(target, int):
            target = hash(target)

        if target not in self.leaves:
            raise ValueError("Target not found in the Merkle tree")

        leaf_index = self.leaves.index(target)
        proof = []

        for level in range(len(self.levels) - 1):
            sibling_index = leaf_index + 1 if leaf_index % 2 == 0 else leaf_index - 1
            if sibling_index < len(self.levels[level]):
                sibling_hash = self.levels[level][sibling_index]
                proof.append(sibling_hash)
            leaf_index //= 2

        return proof

    def verify_proof(self, target: Any, proof: MerkleProof) -> Any:
        """Verify a Merkle proof."""
        if not isinstance(target, int):
            target = hash(target)

        leaf_index = self.leaves.index(target)

        for i, sibling_hash in enumerate(proof):
            is_left = (leaf_index // (2**i)) % 2 == 0
            if is_left:
                target = self.hash_method.hash(target, sibling_hash)
            else:
                target = self.hash_method.hash(sibling_hash, target)

        return target == self.root_hash

    def as_dict(self) -> dict:
        return {
            "leaves": self.leaves,
            "levels": self.levels,
            "root_hash": self.root_hash,
            "hash_method": self.hash_method.name,
        }
