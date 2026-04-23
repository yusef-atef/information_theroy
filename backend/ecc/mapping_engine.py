"""
mapping_engine.py — Per-User Galois Field Mapping Table

Each user gets a unique bijective map from printable ASCII → GF(256).
This means the RS codeword for "password123" looks completely different
for user A vs user B, defeating Rainbow Table / multi-target attacks.

The mapping is derived from a random 32-byte seed stored (encrypted)
in the user's database record.
"""

import os
import json
import hashlib
import random


# Printable ASCII characters used as the password alphabet.
# We exclude the '*' wildcard (reserved for erasure notation).
_PRINTABLE: list[int] = [c for c in range(32, 127) if c != ord('*')]

# Fixed password block length (padded/truncated before RS encoding).
PASSWORD_BLOCK_LEN: int = 16

# Number of RS parity symbols (must be even; t = N_PARITY // 2 errors correctable).
N_PARITY: int = 4


def generate_mapping(seed: bytes) -> dict[int, int]:
    """
    Generate a bijective ASCII-value → GF(256) mapping from a 32-byte seed.

    The mapping shuffles the 94 printable (non-wildcard) ASCII values into
    a subset of GF(256) symbols [1..255] using a seeded Fisher-Yates shuffle.

    Args:
        seed: 32 bytes of cryptographically random data (per-user)

    Returns:
        mapping: dict {ascii_int → gf256_int}
    """
    # Use SHA-256 of seed as the PRNG seed for reproducibility
    rng = random.Random(hashlib.sha256(seed).digest())
    gf_symbols = list(range(1, 256))     # [1..255] — avoid 0 (the zero element)
    rng.shuffle(gf_symbols)
    mapping = {ascii_val: gf_symbols[i] for i, ascii_val in enumerate(_PRINTABLE)}
    return mapping


def generate_inverse_mapping(mapping: dict[int, int]) -> dict[int, int]:
    """Return the inverse mapping: GF(256) symbol → ASCII value."""
    return {v: k for k, v in mapping.items()}


def encode_password(password: str, mapping: dict[int, int]) -> list[int]:
    """
    Convert a plaintext password string to a fixed-length list of GF(256) symbols.

    - Truncates to PASSWORD_BLOCK_LEN characters.
    - Pads shorter passwords with the GF symbol for ASCII space (0x20).
    - Each character is mapped through the user-specific mapping table.

    Args:
        password: plaintext password (max PASSWORD_BLOCK_LEN chars, no '*')
        mapping:  user-specific ASCII → GF(256) mapping

    Returns:
        symbols: list of PASSWORD_BLOCK_LEN GF(256) integers

    Raises:
        ValueError: if a character is not in the mapping table
    """
    # Trim to block length
    pw = password[:PASSWORD_BLOCK_LEN]
    # Pad with space character
    pad_char = ord(' ')
    pad_symbol = mapping.get(pad_char, 1)
    symbols = []
    for ch in pw:
        ascii_val = ord(ch)
        if ascii_val not in mapping:
            raise ValueError(
                f"Character '{ch}' (0x{ascii_val:02X}) is not in the mapping table. "
                "Use only printable ASCII characters (excluding '*')."
            )
        symbols.append(mapping[ascii_val])
    # Pad to block length
    symbols += [pad_symbol] * (PASSWORD_BLOCK_LEN - len(symbols))
    return symbols


def decode_symbols(symbols: list[int], inverse_mapping: dict[int, int]) -> str:
    """
    Convert a list of GF(256) symbols back to a plaintext password string.
    Strips trailing padding (space characters).

    Args:
        symbols:         list of GF(256) integers (length PASSWORD_BLOCK_LEN)
        inverse_mapping: GF(256) → ASCII mapping

    Returns:
        password string (trailing spaces removed)
    """
    chars = []
    for sym in symbols:
        ascii_val = inverse_mapping.get(sym)
        if ascii_val is None:
            raise ValueError(f"GF symbol {sym} not found in inverse mapping")
        chars.append(chr(ascii_val))
    return ''.join(chars).rstrip(' ')


def encode_password_with_erasures(
    password: str,
    mapping: dict[int, int],
    erasure_char: str = '*',
) -> tuple[list[int], list[int]]:
    """
    Encode a password that may contain erasure wildcards ('*').

    Each '*' in the password is treated as an unknown character (erasure).
    The corresponding GF symbol is set to 0 (the GF additive identity).

    Args:
        password:     password with optional '*' wildcards
        mapping:      user-specific ASCII → GF(256) mapping
        erasure_char: the wildcard character (default '*')

    Returns:
        (symbols, erasure_positions): encoded symbols and list of erasure indices
    """
    pw = password[:PASSWORD_BLOCK_LEN]
    pad_char = ord(' ')
    pad_symbol = mapping.get(pad_char, 1)

    symbols: list[int] = []
    erasure_positions: list[int] = []

    for i, ch in enumerate(pw):
        if ch == erasure_char:
            symbols.append(0)  # placeholder; will be corrected by RS decoder
            erasure_positions.append(i)
        else:
            ascii_val = ord(ch)
            if ascii_val not in mapping:
                raise ValueError(
                    f"Character '{ch}' (0x{ascii_val:02X}) not in mapping table."
                )
            symbols.append(mapping[ascii_val])

    # Pad to block length (trailing pad positions are also erasures if needed)
    symbols += [pad_symbol] * (PASSWORD_BLOCK_LEN - len(symbols))

    # Append n_parity placeholder zeros (they will be filled by the stored codeword
    # during decoding, but set to 0 here so the caller knows the parity region)
    return symbols, erasure_positions


def mapping_to_json(mapping: dict[int, int]) -> str:
    """Serialize a mapping table to a JSON string for storage."""
    return json.dumps({str(k): v for k, v in mapping.items()})


def mapping_from_json(data: str) -> dict[int, int]:
    """Deserialize a mapping table from a JSON string."""
    return {int(k): v for k, v in json.loads(data).items()}


def generate_user_seed() -> bytes:
    """Generate a fresh 32-byte cryptographically random seed for a new user."""
    return os.urandom(32)
