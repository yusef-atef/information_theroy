"""
galois_field.py — GF(2^8) Arithmetic for Reed-Solomon ECC

Implements Galois Field arithmetic over GF(256) using the standard
irreducible polynomial x^8 + x^4 + x^3 + x^2 + 1  (0x11D).

All 256-element log and antilog tables are precomputed at import time
for O(1) multiply/divide operations.
"""

# ---------------------------------------------------------------------------
# Primitive polynomial: x^8 + x^4 + x^3 + x^2 + 1  →  0x11D
# Generator element: α = 2  (primitive root)
# ---------------------------------------------------------------------------
_PRIM_POLY = 0x11D
_FIELD_SIZE = 256

# Precompute log (discrete log base α) and antilog (exp) tables
_LOG: list[int] = [0] * _FIELD_SIZE
_EXP: list[int] = [0] * (_FIELD_SIZE * 2)   # doubled for wrap-around shortcut

_x = 1
for _i in range(_FIELD_SIZE - 1):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x >= _FIELD_SIZE:
        _x ^= _PRIM_POLY
        _x &= 0xFF

# Mirror the first 255 entries into positions [255..509] to avoid modulo in mul
for _i in range(_FIELD_SIZE - 1, _FIELD_SIZE * 2):
    _EXP[_i] = _EXP[_i - (_FIELD_SIZE - 1)]


# ---------------------------------------------------------------------------
# Core GF(256) operations (module-level functions for speed)
# ---------------------------------------------------------------------------

def gf_add(a: int, b: int) -> int:
    """Addition in GF(256) — same as XOR."""
    return a ^ b


def gf_sub(a: int, b: int) -> int:
    """Subtraction in GF(256) — identical to addition (char 2 field)."""
    return a ^ b


def gf_mul(a: int, b: int) -> int:
    """Multiplication using precomputed log/antilog tables. O(1)."""
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def gf_div(a: int, b: int) -> int:
    """Division a / b in GF(256). Raises ZeroDivisionError if b == 0."""
    if b == 0:
        raise ZeroDivisionError("Division by zero in GF(256)")
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % (_FIELD_SIZE - 1)]


def gf_pow(a: int, power: int) -> int:
    """Raise a to an integer power in GF(256)."""
    if power == 0:
        return 1
    if a == 0:
        return 0
    return _EXP[(_LOG[a] * power) % (_FIELD_SIZE - 1)]


def gf_inv(a: int) -> int:
    """Multiplicative inverse of a in GF(256)."""
    if a == 0:
        raise ZeroDivisionError("No inverse of 0 in GF(256)")
    return _EXP[(_FIELD_SIZE - 1) - _LOG[a]]


# ---------------------------------------------------------------------------
# Polynomial operations (polynomials stored as lists, index 0 = highest degree)
# ---------------------------------------------------------------------------

def poly_scale(poly: list[int], scalar: int) -> list[int]:
    """Multiply every coefficient of poly by scalar in GF(256)."""
    return [gf_mul(c, scalar) for c in poly]


def poly_add(p: list[int], q: list[int]) -> list[int]:
    """Add two polynomials in GF(256) (XOR coefficient-wise)."""
    # Align lengths
    if len(p) < len(q):
        p = [0] * (len(q) - len(p)) + p
    elif len(q) < len(p):
        q = [0] * (len(p) - len(q)) + q
    return [gf_add(a, b) for a, b in zip(p, q)]


def poly_mul(p: list[int], q: list[int]) -> list[int]:
    """Multiply two polynomials in GF(256)."""
    result = [0] * (len(p) + len(q) - 1)
    for i, cp in enumerate(p):
        for j, cq in enumerate(q):
            result[i + j] ^= gf_mul(cp, cq)
    return result


def poly_eval(poly: list[int], x: int) -> int:
    """Evaluate polynomial at x using Horner's method."""
    result = 0
    for coeff in poly:
        result = gf_add(gf_mul(result, x), coeff)
    return result


def poly_div(dividend: list[int], divisor: list[int]) -> tuple[list[int], list[int]]:
    """
    Polynomial division in GF(256).
    Returns (quotient, remainder).
    """
    msg_out = list(dividend)
    for i in range(len(dividend) - (len(divisor) - 1)):
        coef = msg_out[i]
        if coef != 0:
            for j in range(1, len(divisor)):
                if divisor[j] != 0:
                    msg_out[i + j] ^= gf_mul(divisor[j], coef)
    separator = -(len(divisor) - 1)
    return msg_out[:separator], msg_out[separator:]
