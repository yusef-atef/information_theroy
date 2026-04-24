"""
ecc_auth.py — Top-Level ECC Authentication API

This module is the public interface for the SecureCorrect authentication layer.
It wires together the mapping engine and Reed-Solomon codec to provide:

  - register_password():      encode and store a master password
  - verify_and_correct():     accept a noisy/erased input and attempt correction
"""

from dataclasses import dataclass
from backend.ecc.mapping_engine import (
    generate_user_seed,
    generate_mapping,
    generate_inverse_mapping,
    encode_password,
    encode_password_with_erasures,
    decode_symbols,
    mapping_to_json,
    mapping_from_json,
    PASSWORD_BLOCK_LEN,
)
from backend.ecc.reed_solomon import rs_encode, rs_decode, ReedSolomonError


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RegistrationBundle:
    """
    The artefacts produced at registration time.
    The codeword and serialized mapping are persisted (encrypted) in the DB.
    The seed is stored alongside for auditability.
    """
    codeword: list[int]       # length = PASSWORD_BLOCK_LEN + N_PARITY
    mapping_json: str         # serialized per-user mapping (must be stored encrypted)
    seed_hex: str             # hex of the 32-byte seed (for backup/recovery)


@dataclass
class CorrectionResult:
    """Result returned by verify_and_correct()."""
    success: bool
    corrected_password: str | None   # None on failure
    n_errors_corrected: int          # number of symbol errors fixed
    n_erasures_filled: int           # number of wildcard positions filled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_password(plaintext_password: str) -> RegistrationBundle:
    """
    Encode and package a master password for secure storage.

    Steps:
        1. Generate a fresh per-user random seed.
        2. Build the user-specific GF(256) mapping from the seed.
        3. Encode the password into GF(256) symbols using the mapping.
        4. Apply Reed-Solomon encoding to produce a codeword with parity.

    Args:
        plaintext_password: the user's master password (max 16 chars)

    Returns:
        RegistrationBundle with the codeword, serialized mapping, and seed hex
    """
    seed = generate_user_seed()
    mapping = generate_mapping(seed)
    message_symbols = encode_password(plaintext_password, mapping)
    
    # Calculate dynamic parity: 25% of length -> n_parity = max(4, (len // 4) * 2)
    actual_len = min(len(plaintext_password), PASSWORD_BLOCK_LEN)
    n_parity = max(4, (actual_len // 4) * 2)
    # Must be even
    if n_parity % 2 != 0:
        n_parity += 1
        
    codeword = rs_encode(message_symbols, n_parity)

    return RegistrationBundle(
        codeword=codeword,
        mapping_json=mapping_to_json(mapping),
        seed_hex=seed.hex(),
    )


def verify_and_correct(
    input_password: str,
    stored_codeword: list[int],
    mapping_json: str,
    erasure_char: str = '*',
) -> CorrectionResult:
    """
    Attempt to correct a potentially-erroneous password input.

    The input may contain:
      - Character errors (wrong character at a known-to-be-wrong position)
      - Erasures (wildcard '*' meaning "I forgot this character")

    Correction capacity (Dynamic):
      - Pure errors:   up to n_parity / 2
      - Pure erasures: up to n_parity
      - Mixed:         2 * errors + erasures ≤ n_parity

    Steps:
        1. Encode the input password into GF(256) symbols (with erasure marking).
        2. Graft in the stored parity symbols from the stored codeword.
        3. Run the RS decoder with the erasure positions.
        4. Decode the corrected symbols back to a plaintext string.

    Args:
        input_password:   the password the user typed (may have '*' wildcards)
        stored_codeword:  the codeword produced at registration (from DB)
        mapping_json:     the user's serialized mapping table (from DB)
        erasure_char:     the character used as a wildcard (default '*')

    Returns:
        CorrectionResult — check .success before using .corrected_password
    """
    mapping = mapping_from_json(mapping_json)
    inverse_mapping = generate_inverse_mapping(mapping)

    # 1. Encode input (with erasure markers)
    try:
        message_symbols, erasure_positions = encode_password_with_erasures(
            input_password, mapping, erasure_char
        )
    except ValueError:
        return CorrectionResult(
            success=False,
            corrected_password=None,
            n_errors_corrected=0,
            n_erasures_filled=0,
        )

    # 2. Build received codeword: message symbols + STORED parity symbols
    #    This is key: the stored parity anchors the RS code to the correct codeword.
    received = message_symbols + stored_codeword[PASSWORD_BLOCK_LEN:]

    # Erasure positions are within the message region (indices 0..PASSWORD_BLOCK_LEN-1)
    # They are already correctly indexed from encode_password_with_erasures.

    # 3. RS decode
    try:
        n_parity = len(stored_codeword) - PASSWORD_BLOCK_LEN
        corrected_message = rs_decode(
            received,
            erasure_positions=erasure_positions,
            n_parity=n_parity,
        )
    except ReedSolomonError:
        return CorrectionResult(
            success=False,
            corrected_password=None,
            n_errors_corrected=0,
            n_erasures_filled=len(erasure_positions),
        )

    # 4. Decode symbols back to string
    try:
        corrected_password = decode_symbols(corrected_message, inverse_mapping)
    except ValueError:
        return CorrectionResult(
            success=False,
            corrected_password=None,
            n_errors_corrected=0,
            n_erasures_filled=0,
        )

    # Append any characters beyond the ECC block length (these are not protected by ECC)
    if len(input_password) > PASSWORD_BLOCK_LEN:
        corrected_password += input_password[PASSWORD_BLOCK_LEN:]

    # Count actual corrections: positions where input symbol ≠ corrected symbol
    n_errors = sum(
        1 for i, (orig, corr) in enumerate(zip(message_symbols, corrected_message))
        if orig != corr and i not in erasure_positions
    )

    return CorrectionResult(
        success=True,
        corrected_password=corrected_password,
        n_errors_corrected=n_errors,
        n_erasures_filled=len(erasure_positions),
    )


def quick_check_codeword(stored_codeword: list[int]) -> bool:
    """
    Sanity check: verify the stored codeword itself has valid RS parity.
    Useful at registration time to catch encoding bugs.
    """
    try:
        n_parity = len(stored_codeword) - PASSWORD_BLOCK_LEN
        rs_decode(stored_codeword, erasure_positions=[], n_parity=n_parity)
        return True
    except ReedSolomonError:
        return False
