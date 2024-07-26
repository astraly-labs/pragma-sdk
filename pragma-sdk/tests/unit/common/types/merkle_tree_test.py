import pytest

from starknet_py.hash.hash_method import HashMethod

from pragma_sdk.common.types.merkle_tree import MerkleTree


@pytest.fixture
def sample_merkle_tree() -> MerkleTree:
    leaves = [1, 2, 3, 4]
    return MerkleTree(leaves, HashMethod.PEDERSEN)


def test_get_proof(sample_merkle_tree: MerkleTree):
    proof = sample_merkle_tree.get_proof(2)
    assert isinstance(proof, list)
    assert all(isinstance(item, int) for item in proof)


def test_get_proof_non_existent(sample_merkle_tree: MerkleTree):
    with pytest.raises(ValueError, match="Target not found in the Merkle tree"):
        sample_merkle_tree.get_proof(5)


def test_verify_proof(sample_merkle_tree: MerkleTree):
    proof = sample_merkle_tree.get_proof(2)
    assert sample_merkle_tree.verify_proof(2, proof)


def test_verify_proof_invalid(sample_merkle_tree: MerkleTree):
    proof = sample_merkle_tree.get_proof(2)
    assert not sample_merkle_tree.verify_proof(3, proof)


def test_as_dict(sample_merkle_tree: MerkleTree):
    tree_dict = sample_merkle_tree.as_dict()
    assert isinstance(tree_dict, dict)
    assert "leaves" in tree_dict
    assert "levels" in tree_dict
    assert "root_hash" in tree_dict
    assert "hash_method" in tree_dict


def test_empty_tree():
    with pytest.raises(
        ValueError, match="Cannot build Merkle tree from an empty list of leaves."
    ):
        MerkleTree([], HashMethod.PEDERSEN)


def test_single_leaf_tree():
    tree = MerkleTree([1], HashMethod.PEDERSEN)
    assert tree.root_hash == 1
    assert tree.levels == [[1]]


def test_odd_number_of_leaves():
    leaves = [1, 2, 3]
    tree = MerkleTree(leaves, HashMethod.PEDERSEN)
    assert len(tree.levels) > 1
    assert tree.levels[0] == leaves
