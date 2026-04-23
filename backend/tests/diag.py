"""Diagnostic: trace through a single-error decode step by step."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from backend.ecc.galois_field import gf_pow, gf_inv, gf_mul, gf_div
from backend.ecc.reed_solomon import (
    rs_encode, _syndromes, _berlekamp_massey, _chien_search,
    _forney, _deriv, _mul, _eval, _be_poly_eval
)

N = 4
msg = [42, 17, 200, 88, 3, 156, 71, 0, 255, 100, 9, 33, 188, 77, 44, 210]
cw  = rs_encode(msg, N)
print("Original codeword:", cw)

# Introduce 1 error at position 3
cw_err = list(cw)
cw_err[3] ^= 0xFF
print("Corrupted at pos 3:", cw_err)

synd = _syndromes(cw_err, N)
print("Syndromes:", synd)

sigma = _berlekamp_massey(synd)
print("Locator sigma (LE):", sigma)

error_pos = _chien_search(sigma, len(cw_err))
print("Error positions:", error_pos)

omega = _mul(synd, sigma)[:N]
print("Omega (LE):", omega)

sp = _deriv(sigma)
print("Sigma' (LE):", sp)

if error_pos:
    pos = error_pos[0]
    xi = gf_pow(2, pos)
    xi_inv = gf_inv(xi)
    num = _eval(omega, xi_inv)
    den = _eval(sp, xi_inv)
    mag = gf_mul(xi, gf_div(num, den)) if den != 0 else 0
    print(f"pos={pos}, xi={xi}, xi_inv={xi_inv}, num={num}, den={den}, mag={mag}")
    print(f"Expected magnitude (original^corrupted): {cw[3] ^ cw_err[3]}")

    # Apply and check
    cw_fixed = list(cw_err)
    cw_fixed[pos] ^= mag
    final_synd = _syndromes(cw_fixed, N)
    print("Final syndromes after fix:", final_synd)
    print("Fixed == original?", cw_fixed[:16] == msg)
