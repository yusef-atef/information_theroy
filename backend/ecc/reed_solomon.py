"""
reed_solomon.py — Reed-Solomon Encoder / Decoder over GF(256)

Uses a consistent little-endian (LE) polynomial convention for the decoder,
while matching the big-endian (BE) convention of galois_field.py for encoding.

Correction capacity with n_parity symbols:
  2*e + r <= n_parity
  where e is number of errors and r is number of erasures.
"""

from backend.ecc.galois_field import (
    gf_add, gf_mul, gf_div, gf_pow, gf_inv,
    poly_eval as _be_poly_eval,
    poly_mul as _be_poly_mul,
    poly_div as _be_poly_div
)


class ReedSolomonError(Exception):
    """Raised when RS decoding cannot correct the received word."""
    pass


# ---------------------------------------------------------------------------
# Little-endian (LE) polynomial helpers (index i = coeff of x^i)
# ---------------------------------------------------------------------------

def _le_poly_add(p: list[int], q: list[int]) -> list[int]:
    res = [0] * max(len(p), len(q))
    for i in range(len(res)):
        a = p[i] if i < len(p) else 0
        b = q[i] if i < len(q) else 0
        res[i] = a ^ b
    return res


def _le_poly_mul(p: list[int], q: list[int]) -> list[int]:
    res = [0] * (len(p) + len(q) - 1)
    for i, pi in enumerate(p):
        if pi == 0: continue
        for j, qj in enumerate(q):
            res[i + j] ^= gf_mul(pi, qj)
    return res


def _le_poly_scale(p: list[int], s: int) -> list[int]:
    return [gf_mul(pi, s) for pi in p]


def _le_poly_eval(p: list[int], x: int) -> int:
    """Evaluate LE polynomial at x using Horner's method."""
    res = 0
    for c in reversed(p):
        res = gf_add(gf_mul(res, x), c)
    return res


# ---------------------------------------------------------------------------
# Encode (Big-endian)
# ---------------------------------------------------------------------------

def rs_encode(message: list[int], n_parity: int) -> list[int]:
    """Append n_parity Reed-Solomon check symbols to message."""
    # Generator g(x) = prod_{i=0}^{n-1} (x + alpha^i) in BE
    gen = [1]
    for i in range(n_parity):
        gen = _be_poly_mul(gen, [1, gf_pow(2, i)])
    
    padded = message + [0] * n_parity
    _, remainder = _be_poly_div(padded, gen)
    
    # Ensure parity is exactly n_parity long
    parity = [0] * (n_parity - len(remainder)) + remainder
    return message + parity


# ---------------------------------------------------------------------------
# Decode (Little-endian syndromes & locator)
# ---------------------------------------------------------------------------

def rs_decode(codeword: list[int],
              erasure_positions: list[int] | None = None,
              n_parity: int = 4) -> list[int]:
    """
    Decode and correct a received codeword using Berlekamp-Massey + Forney.
    """
    if erasure_positions is None:
        erasure_positions = []
    
    n = len(codeword)
    
    # 1. Syndromes S_i = C(alpha^i)
    # codeword is BE, so we use _be_poly_eval
    synd = [_be_poly_eval(codeword, gf_pow(2, i)) for i in range(n_parity)]
    if all(s == 0 for s in synd):
        return codeword[:-n_parity]
    
    # 2. Erasure locator Gamma(z)
    gamma = [1]
    for pos in erasure_positions:
        # X = alpha^(n-1-pos)
        X = gf_pow(2, n - 1 - pos)
        gamma = _le_poly_mul(gamma, [1, X])
    
    # 3. Forney syndromes S'(z) = S(z) * Gamma(z)
    # S(z) = S_0 + S_1 z + ...
    S_prime = _le_poly_mul(synd, gamma)
    
    # Error syndromes for BM start at index n_erasures
    n_erasures = len(erasure_positions)
    error_synd = S_prime[n_erasures:n_parity]
    
    # 4. Berlekamp-Massey on error syndromes
    sigma_err = [1]
    B = [1]
    L = 0
    m = 1
    prev_discrepancy = 1
    
    for i in range(len(error_synd)):
        d = error_synd[i]
        for j in range(1, L + 1):
            if j < len(sigma_err):
                d ^= gf_mul(sigma_err[j], error_synd[i - j])
        
        if d == 0:
            m += 1
        elif 2 * L <= i:
            T = list(sigma_err)
            factor = gf_div(d, prev_discrepancy)
            zmB = [0] * m + B
            sigma_err = _le_poly_add(sigma_err, _le_poly_scale(zmB, factor))
            L = i + 1 - L
            B = T
            prev_discrepancy = d
            m = 1
        else:
            factor = gf_div(d, prev_discrepancy)
            zmB = [0] * m + B
            sigma_err = _le_poly_add(sigma_err, _le_poly_scale(zmB, factor))
            m += 1
            
    # 5. Full locator sigma(z) = sigma_err(z) * gamma(z)
    sigma = _le_poly_mul(sigma_err, gamma)
    
    # 6. Find all error/erasure positions via Chien search
    all_error_pos = []
    for i in range(n):
        X_inv = gf_inv(gf_pow(2, n - 1 - i))
        if _le_poly_eval(sigma, X_inv) == 0:
            all_error_pos.append(i)
            
    if len(all_error_pos) > n_parity:
        raise ReedSolomonError("Correction capacity exceeded")

    # 7. Forney Algorithm for magnitudes
    # Omega(z) = S(z) * sigma(z) mod z^n_parity
    Omega = _le_poly_mul(synd, sigma)[:n_parity]
    
    # sigma'(z)
    sigma_prime = [0] * (len(sigma) - 1)
    for i in range(1, len(sigma)):
        if i % 2 == 1:
            sigma_prime[i - 1] = sigma[i]
    
    new_cw = list(codeword)
    for i in all_error_pos:
        X = gf_pow(2, n - 1 - i)
        X_inv = gf_inv(X)
        num = _le_poly_eval(Omega, X_inv)
        den = _le_poly_eval(sigma_prime, X_inv)
        if den == 0:
            continue
        # magnitude e_i = X * Omega(X_inv) / sigma_prime(X_inv)
        mag = gf_mul(X, gf_div(num, den))
        new_cw[i] ^= mag
        
    # Final verification
    final_synd = [_be_poly_eval(new_cw, gf_pow(2, j)) for j in range(n_parity)]
    if any(s != 0 for s in final_synd):
        raise ReedSolomonError("Reed-Solomon correction failed")
        
    return new_cw[:-n_parity]
