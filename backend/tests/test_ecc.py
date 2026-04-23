"""
tests/test_ecc.py — Unit Tests for the ECC Math Core

Tests:
  - GF(256) arithmetic identities
  - RS encode / decode round-trip (no errors)
  - RS decode with 1 error
  - RS decode with 2 errors (at capacity)
  - RS decode with erasures (wildcards)
  - Mixed errors + erasures
  - Failure case: too many errors raises ReedSolomonError
  - Full ECC auth: register → verify_and_correct
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.ecc.galois_field import gf_add, gf_mul, gf_div, gf_pow, gf_inv
from backend.ecc.reed_solomon import rs_encode, rs_decode, ReedSolomonError
from backend.ecc.mapping_engine import (
    generate_mapping, generate_user_seed,
    encode_password, decode_symbols, generate_inverse_mapping,
    encode_password_with_erasures, PASSWORD_BLOCK_LEN, N_PARITY,
)
from backend.ecc.ecc_auth import register_password, verify_and_correct


# ---------------------------------------------------------------------------
# GF(256) arithmetic
# ---------------------------------------------------------------------------

class TestGF256:
    def test_add_is_xor(self):
        assert gf_add(0b10110011, 0b01001101) == (0b10110011 ^ 0b01001101)

    def test_add_identity(self):
        for x in [0, 1, 127, 255]:
            assert gf_add(x, 0) == x

    def test_add_self_is_zero(self):
        for x in [1, 42, 255]:
            assert gf_add(x, x) == 0

    def test_mul_by_zero(self):
        assert gf_mul(255, 0) == 0
        assert gf_mul(0, 128) == 0

    def test_mul_by_one(self):
        for x in [1, 50, 200, 255]:
            assert gf_mul(x, 1) == x

    def test_mul_commutativity(self):
        assert gf_mul(17, 42) == gf_mul(42, 17)

    def test_div_inverse_of_mul(self):
        a, b = 37, 121
        assert gf_div(gf_mul(a, b), b) == a

    def test_pow_zero(self):
        assert gf_pow(99, 0) == 1

    def test_pow_one(self):
        assert gf_pow(7, 1) == 7

    def test_inv_correctness(self):
        for x in [1, 2, 128, 255]:
            assert gf_mul(x, gf_inv(x)) == 1

    def test_div_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            gf_div(5, 0)


# ---------------------------------------------------------------------------
# Reed-Solomon encode / decode
# ---------------------------------------------------------------------------

N = N_PARITY  # 4 parity symbols → t=2 error correction


class TestReedSolomon:
    def _sample_message(self) -> list[int]:
        return [42, 17, 200, 88, 3, 156, 71, 0, 255, 100,
                9,  33, 188, 77, 44, 210]  # PASSWORD_BLOCK_LEN = 16

    def test_encode_length(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        assert len(cw) == len(msg) + N

    def test_clean_decode(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        recovered = rs_decode(cw, n_parity=N)
        assert recovered == msg

    def test_single_error(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        cw[3] ^= 0xFF          # flip all bits at position 3
        recovered = rs_decode(cw, n_parity=N)
        assert recovered == msg

    def test_two_errors(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        cw[0] ^= 0xAB
        cw[15] ^= 0x55
        recovered = rs_decode(cw, n_parity=N)
        assert recovered == msg

    def test_three_errors_raises(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        cw[0] ^= 1
        cw[5] ^= 1
        cw[10] ^= 1
        with pytest.raises(ReedSolomonError):
            rs_decode(cw, n_parity=N)

    def test_single_erasure(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        cw[7] = 0              # erase position 7
        recovered = rs_decode(cw, erasure_positions=[7], n_parity=N)
        assert recovered == msg

    def test_four_erasures(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        erased = [0, 4, 8, 12]
        for pos in erased:
            cw[pos] = 0
        recovered = rs_decode(cw, erasure_positions=erased, n_parity=N)
        assert recovered == msg

    def test_mixed_error_and_erasure(self):
        """1 error + 2 erasures: 2*1 + 2 = 4 ≤ 4 (at capacity)."""
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        cw[2] ^= 0x33           # error
        cw[9] = 0               # erasure
        cw[14] = 0              # erasure
        recovered = rs_decode(cw, erasure_positions=[9, 14], n_parity=N)
        assert recovered == msg

    def test_too_many_erasures_raises(self):
        msg = self._sample_message()
        cw = rs_encode(msg, N)
        for pos in [0, 1, 2, 3, 4]:
            cw[pos] = 0
        with pytest.raises(ReedSolomonError):
            rs_decode(cw, erasure_positions=[0, 1, 2, 3, 4], n_parity=N)


# ---------------------------------------------------------------------------
# Mapping Engine
# ---------------------------------------------------------------------------

class TestMappingEngine:
    def test_encode_decode_roundtrip(self):
        seed = generate_user_seed()
        mapping = generate_mapping(seed)
        inv = generate_inverse_mapping(mapping)
        password = "Hello123"
        symbols = encode_password(password, mapping)
        recovered = decode_symbols(symbols, inv)
        assert recovered == password

    def test_different_seeds_different_mappings(self):
        s1, s2 = generate_user_seed(), generate_user_seed()
        m1, m2 = generate_mapping(s1), generate_mapping(s2)
        # Very unlikely (1/255 chance) that ord('A') maps to same symbol
        assert m1[ord('A')] != m2[ord('A')] or m1[ord('B')] != m2[ord('B')]

    def test_erasure_encoding(self):
        seed = generate_user_seed()
        mapping = generate_mapping(seed)
        password = "pass*ord"  # one erasure at position 4
        symbols, erasures = encode_password_with_erasures(password, mapping)
        assert 4 in erasures
        assert symbols[4] == 0     # erased position is zero
        assert len(symbols) == PASSWORD_BLOCK_LEN

    def test_padding_to_block_length(self):
        seed = generate_user_seed()
        mapping = generate_mapping(seed)
        symbols = encode_password("hi", mapping)
        assert len(symbols) == PASSWORD_BLOCK_LEN


# ---------------------------------------------------------------------------
# Full ECC Auth integration
# ---------------------------------------------------------------------------

class TestECCAuth:
    def test_exact_password_accepted(self):
        bundle = register_password("Correct1")
        result = verify_and_correct("Correct1", bundle.codeword, bundle.mapping_json)
        assert result.success
        assert result.corrected_password == "Correct1"
        assert result.n_errors_corrected == 0

    def test_one_typo_corrected(self):
        bundle = register_password("Correct1")
        # Change one character: 'C' → 'X'
        result = verify_and_correct("Xorrect1", bundle.codeword, bundle.mapping_json)
        assert result.success
        assert result.corrected_password == "Correct1"
        assert result.n_errors_corrected == 1

    def test_two_typos_corrected(self):
        bundle = register_password("Correct1")
        result = verify_and_correct("Xorrect2", bundle.codeword, bundle.mapping_json)
        assert result.success
        assert result.corrected_password == "Correct1"
        assert result.n_errors_corrected == 2

    def test_three_typos_rejected(self):
        bundle = register_password("Correct1")
        result = verify_and_correct("Xorract2", bundle.codeword, bundle.mapping_json)
        assert not result.success
        assert result.corrected_password is None

    def test_one_erasure_corrected(self):
        bundle = register_password("Correct1")
        result = verify_and_correct("*orrect1", bundle.codeword, bundle.mapping_json)
        assert result.success
        assert result.corrected_password == "Correct1"
        assert result.n_erasures_filled == 1

    def test_four_erasures_corrected(self):
        bundle = register_password("Correct1!")
        result = verify_and_correct("****ect1!", bundle.codeword, bundle.mapping_json)
        assert result.success
        assert result.corrected_password == "Correct1!"

    def test_five_erasures_rejected(self):
        bundle = register_password("Correct1!")
        result = verify_and_correct("*****ct1!", bundle.codeword, bundle.mapping_json)
        assert not result.success

    def test_codeword_integrity(self):
        from backend.ecc.ecc_auth import quick_check_codeword
        bundle = register_password("IntegrityCheck")
        assert quick_check_codeword(bundle.codeword)
