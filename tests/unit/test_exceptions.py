"""Unit tests for dai/exceptions.py"""

from dai.exceptions import ChainContinuityError, HashChainError


def test_chain_continuity_error():
    err = ChainContinuityError(
        "broken chain",
        expected_previous_hash="abc",
        actual_previous_hash="def"
    )
    assert err.message == "broken chain"
    assert err.expected_previous_hash == "abc"
    assert err.actual_previous_hash == "def"

def test_hash_chain_error():
    err = HashChainError(
        "hash error",
        expected_hash="a"*64,
        actual_hash="b"*64,
        decision_id="123"
    )
    repr_str = repr(err)
    assert "HashChainError" in repr_str
    assert "123" in repr_str
    assert "a"*16 in repr_str
    assert "b"*16 in repr_str
