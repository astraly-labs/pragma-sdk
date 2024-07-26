from typing import List
from starknet_py.utils.merkle_tree import MerkleTree as StarknetPyMT


MerkleProof = List[int]


class MerkleTree(StarknetPyMT):
    def get_proof(self, target: int) -> MerkleProof:
        """Generate a Merkle proof for the given target."""
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

    def verify_proof(self, target: int, proof: MerkleProof) -> bool:
        """Verify a Merkle proof."""
        if target not in self.leaves:
            return False

        leaf_index = self.leaves.index(target)
        current_hash = target

        for level, sibling_hash in enumerate(proof):
            if leaf_index % 2 == 0:
                current_hash = self.hash_method.hash(current_hash, sibling_hash)
            else:
                current_hash = self.hash_method.hash(sibling_hash, current_hash)
            leaf_index //= 2

        return current_hash == self.root_hash

    def as_dict(self) -> dict:
        return {
            "leaves": self.leaves,
            "levels": self.levels,
            "root_hash": self.root_hash,
            "hash_method": self.hash_method.name,
        }
