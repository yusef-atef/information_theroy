# Source Code Explanation (Line-by-Line)

This document provides a line-by-line explanation of the core algorithms implementing Chapter 18 (Password Correction and Confidentiality).

---

## 1. Authentication Engine (`ecc_auth.py`)

This file is the bridge between the mathematical Reed-Solomon equations and the web application.

```python
def register_password(plaintext_password: str) -> RegistrationBundle:
    # 1. Generate a highly secure random 32-byte seed.
    seed = generate_user_seed()
    
    # 2. Use the seed to create a unique GF(256) mapping. 
    # This prevents Rainbow Table attacks because "A" is mapped to a different mathematical number for every user.
    mapping = generate_mapping(seed)
    
    # 3. Translate the string password into a list of mathematical GF(256) symbols.
    message_symbols = encode_password(plaintext_password, mapping)
    
    # 4. Calculate dynamic parity based on Chapter 18 concepts.
    # We allocate 25% of the password length as parity. The longer the password, the more errors we can correct.
    actual_len = min(len(plaintext_password), PASSWORD_BLOCK_LEN)
    n_parity = max(4, (actual_len // 4) * 2)
    
    # Parity symbols must be an even number for the equation t = N / 2.
    if n_parity % 2 != 0:
        n_parity += 1
        
    # 5. Apply the Reed-Solomon encoding algorithm to generate the Codeword.
    codeword = rs_encode(message_symbols, n_parity)

    # 6. Return the codeword and the mapping table (which will be AES encrypted in the database).
    return RegistrationBundle(
        codeword=codeword,
        mapping_json=mapping_to_json(mapping),
        seed_hex=seed.hex(),
    )
```

```python
def verify_and_correct(
    input_password: str,
    stored_codeword: list[int],
    mapping_json: str,
    erasure_char: str = '*',
) -> CorrectionResult:
    # 1. Reconstruct the user's specific mathematical mapping table from the database JSON.
    mapping = mapping_from_json(mapping_json)
    inverse_mapping = generate_inverse_mapping(mapping)

    # 2. Translate the typed password into symbols. If the user typed '*', we mark its position as an erasure.
    # Erasures are mathematically cheaper to fix than unknown errors.
    try:
        message_symbols, erasure_positions = encode_password_with_erasures(
            input_password, mapping, erasure_char
        )
    except ValueError:
        return CorrectionResult(success=False, ...)

    # 3. Graft the Parity Symbols from the database onto the newly typed message.
    # This creates a "Received Codeword" which is what the Reed-Solomon decoder requires to find deviations.
    received = message_symbols + stored_codeword[PASSWORD_BLOCK_LEN:]

    # 4. Dynamically determine how many parity symbols were used based on the database record length.
    n_parity = len(stored_codeword) - PASSWORD_BLOCK_LEN
    
    # 5. Execute the core mathematical decoder (Berlekamp-Massey and Forney algorithms).
    try:
        corrected_message = rs_decode(
            received,
            erasure_positions=erasure_positions,
            n_parity=n_parity,
        )
    except ReedSolomonError:
        # If the number of errors exceeds the mathematical limit, the equation fails to resolve.
        return CorrectionResult(success=False, ...)

    # 6. Translate the corrected GF(256) mathematical symbols back into a readable string password.
    corrected_password = decode_symbols(corrected_message, inverse_mapping)

    # 7. Provide statistics on how many errors/erasures were successfully fixed.
    n_errors = sum(1 for i, (orig, corr) in enumerate(zip(message_symbols, corrected_message)) if orig != corr and i not in erasure_positions)
    return CorrectionResult(success=True, corrected_password=corrected_password, ...)
```

---

## 2. Galois Field Mapping (`mapping_engine.py`)

This file implements the substitution of ASCII characters into the Galois Field.

```python
def generate_mapping(seed: bytes) -> dict[int, int]:
    # 1. Use the 32-byte seed to initialize a Deterministic Random Number Generator (PRNG).
    # This guarantees that the exact same seed always produces the exact same mapping.
    rng = random.Random(hashlib.sha256(seed).digest())
    
    # 2. Generate a list of all non-zero elements in GF(256), from 1 to 255.
    # We avoid 0 because 0 is reserved for mathematical 'erasures' in the decoder.
    gf_symbols = list(range(1, 256))
    
    # 3. Cryptographically shuffle the GF(256) symbols.
    rng.shuffle(gf_symbols)
    
    # 4. Assign each printable ASCII character to a shuffled GF(256) symbol.
    mapping = {ascii_val: gf_symbols[i] for i, ascii_val in enumerate(_PRINTABLE)}
    return mapping
```

```python
def encode_password_with_erasures(password: str, mapping: dict[int, int], erasure_char: str = '*') -> tuple[list[int], list[int]]:
    # 1. Trim the password to the maximum block length (64).
    pw = password[:PASSWORD_BLOCK_LEN]
    
    # 2. Determine the mathematical symbol for 'space', used to pad short passwords.
    pad_char = ord(' ')
    pad_symbol = mapping.get(pad_char, 1)

    symbols = []
    erasure_positions = []

    # 3. Loop over every character in the typed password.
    for i, ch in enumerate(pw):
        if ch == erasure_char:
            # 4. If the character is a wildcard ('*'), we record its exact index position.
            # We insert the number '0', which mathematically signifies 'unknown data' to the Forney algorithm.
            erasure_positions.append(i)
            symbols.append(0)
        else:
            # 5. Otherwise, convert the letter to its corresponding GF(256) integer.
            symbols.append(mapping[ord(ch)])

    # 6. Pad the remaining blocks with the space symbol so the math matrix is the correct size.
    symbols += [pad_symbol] * (PASSWORD_BLOCK_LEN - len(symbols))
    return symbols, erasure_positions
```
