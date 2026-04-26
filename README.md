# SecureCorrect 🛡️
**Fault-Tolerant, Zero-Knowledge Hybrid Cloud Storage System**

## 📖 Executive Summary
**SecureCorrect** is an advanced, cross-platform encrypted storage platform designed to solve a critical usability flaw in modern Zero-Knowledge architectures: **password loss due to minor typographical errors**. 

Traditional End-to-End Encrypted (E2EE) systems are extremely brittle; a single wrong character in a master password results in total data loss. SecureCorrect solves this by integrating **Reed-Solomon Error-Correcting Codes (ECC)** at the authentication layer. This allows the system to mathematically reconstruct a user's master password even if they mistype characters or explicitly mark forgotten characters using wildcards (`*`), all without the server ever knowing the plaintext password.

---

## 🧠 1. Deep Technical Architecture: The Cryptographic Engine

### 1.1. Per-User Galois Field Mapping (GF(256))
To apply Reed-Solomon equations to text, characters must be mapped to a finite mathematical field. SecureCorrect uses **GF(256)**.
*   **The Problem:** If every user used the same ASCII-to-GF(256) mapping, attackers could build "Rainbow Tables" to guess passwords based on intercepted codewords.
*   **The Solution:** At registration, the frontend generates a cryptographically secure 32-byte `seed`. This seed generates a **unique, bijective (1-to-1) mapping table** mapping printable ASCII characters to GF(256) symbols. 
*   **Result:** The password "password123" translates to a completely different mathematical polynomial for User A than it does for User B, neutralizing multi-target attacks.

### 1.2. Dynamic Reed-Solomon Error Correction (ECC)
Reed-Solomon is a block-based error-correcting code. SecureCorrect uses it creatively for passwords.
*   **Dynamic Parity Scaling:** The system dynamically calculates the required error tolerance based on the password length. The system allocates a budget of exactly **25% of the password's length**.
    *   *Equation:* `Parity Symbols (n_parity) = (Password_Length // 4) * 2`
*   **Errors vs. Erasures:** 
    *   **Error (Typo):** The user types the wrong character, but the system doesn't know *which* character is wrong. Correcting an error costs **2 parity symbols**.
    *   **Erasure (Wildcard `*`):** The user forgot a character and types `*`. The system knows exactly *where* the missing character is. Correcting an erasure costs only **1 parity symbol**.
    *   *Example:* A 64-character password generates 32 parity symbols. The user can make up to 16 blind typos, OR use 32 wildcards, or a mix of both.

### 1.3. Key Derivation & Zero-Knowledge Guarantee
Even with ECC, the backend **never** sees the plaintext password.
1.  **Client-Side Hashing:** Once the ECC engine corrects the password, it is passed through the **Argon2** key-derivation function. Argon2 is memory-hard, making brute-force GPU attacks prohibitively expensive.
2.  **Key Splitting:** The Argon2 hash derives two separate keys:
    *   `Session Key (AES-256):` Used entirely locally on the mobile device to encrypt/decrypt files.
    *   `HMAC Key:` Used to sign requests to the server to prove authenticity without transmitting the password.

---

## ☁️ 2. Hybrid Storage Ecosystem

SecureCorrect features a dual-storage engine, giving users ultimate control over data sovereignty.

### 2.1. Google Drive Integration (Decentralized)
*   **Hidden AppData Folder:** Files are uploaded via Google APIs directly from the user's mobile device to a special, hidden `appDataFolder` in their Google Drive. The user cannot accidentally delete these files from the normal Drive UI.
*   **Silent Token Refresh:** The frontend handles OAuth 2.0 access tokens. A background service intercepts `401 Unauthorized` errors and silently refreshes the token using the Google Sign-In SDK, ensuring uninterrupted uploads.
*   **Server as a Ledger:** The backend server only stores the *Metadata* (Google File ID, AES-GCM IV, MAC Tag, and File Name). The encrypted file bytes never touch the SecureCorrect server.

### 2.2. SecureCorrect Native Storage (Centralized Fallback)
*   If a user opts out of Google Drive, the Flutter app uploads the raw encrypted bytes directly to the SecureCorrect FastAPI backend.
*   The backend stores the encrypted blob in the local file system (`backend/uploads/`) and links the file path to the database.

---

## 🔐 3. Deep Dive: API Endpoints & Request Lifecycles

The backend is built with **FastAPI** leveraging asynchronous processing for high throughput.

### 3.1. Authentication Router (`/routers/auth.py`)

#### `POST /auth/register`
*   **Payload:** Username, Email, RSA-Encrypted Master Password.
*   **Under the Hood:**
    1. Server decrypts the payload using its private RSA key.
    2. Calls `register_password()` which assigns the GF(256) mapping, executes the Reed-Solomon encoder, and generates the `codeword` (Polynomial + Parity).
    3. Hashes the password using Argon2 to act as the ultimate verification lock.
    4. Generates an HMAC key.
*   **Returns:** A success confirmation.

#### `POST /auth/login`
*   **Payload:** Username, Password (potentially containing typos or `*`), Encrypted Session Key.
*   **Under the Hood:**
    1. The backend fetches the user's `codeword` and `mapping table` from the database.
    2. Calls `verify_and_correct()`. It grafts the stored parity symbols onto the incoming typed password.
    3. Runs the **Forney** and **Berlekamp-Massey** algorithms to locate and fix errors.
    4. Compares the newly corrected password against the Argon2 hash.
    5. Generates stateless JWT tokens (Access & Refresh).
*   **Returns:** JWT Tokens, and a metadata payload detailing exactly how many errors/erasures were corrected.

### 3.2. File Management Router (`/routers/files.py`)

#### `POST /files/upload` (Native Server Storage)
*   **Payload:** `multipart/form-data` containing the encrypted file, filename, IV, and GCM Tag.
*   **Under the Hood:** Validates the JWT token, streams the file bytes to the local disk, and inserts the cryptographic metadata into the SQLite `files` table.

#### `POST /files/upload/drive` (Google Drive Metadata Sync)
*   **Payload:** JSON containing `google_file_id`, `filename`, `iv_hex`, `gcm_tag_hex`, `hmac_hex`.
*   **Under the Hood:** This endpoint does *not* accept file bytes. It trusts the client has already uploaded the file to Google Drive. It registers the Google File ID in the database alongside the encryption parameters.

#### `GET /files/`
*   **Under the Hood:** Queries the database for all files belonging to the JWT's `user_id`. Returns a JSON list of objects. Crucially, it tells the client whether a file is stored natively (`storage_key` exists) or on Drive (`google_file_id` exists).

#### `GET /files/download/{file_id}`
*   **Under the Hood:** Streams the file bytes from the local backend storage to the client. (Used only if `google_file_id` is null).

#### `DELETE /files/{file_id}`
*   **Under the Hood:** Removes the database record. If the file was stored locally, it deletes the file from the disk using `os.remove()`. If it was on Drive, the client handles the Drive deletion, and the server simply drops the metadata.

### 3.3. Admin & Telemetry Router (`/routers/admin.py`)

#### `WS /admin/ws` (WebSocket)
*   **Under the Hood:** An asynchronous WebSocket connection. When a user registers or uploads a file, SQLAlchemy triggers broadcast events. The admin dashboard receives instantaneous JSON payloads reflecting live system statistics without requiring HTTP polling.

---

## 📱 4. Frontend Architecture (Flutter)

The mobile application is built using **Flutter** and strictly adheres to the **BLoC (Business Logic Component)** state management pattern.

### 4.1. Real-Time ECC Budget Calculator
The `EccPasswordField` widget listens to the user's keystrokes. It calculates `(Text Length // 4) * 2` to display the dynamic maximum allowed errors. If the user types too many `*` wildcards, the UI blocks further wildcard insertion and changes color, providing instantaneous UX feedback.

### 4.2. Encryption Engine (`crypto_engine.dart`)
All cryptography is handled locally via the `pointycastle` and `encrypt` Dart packages.
*   The file is read into memory as a `Uint8List`.
*   A cryptographically secure random 12-byte IV is generated.
*   AES-GCM encryption is applied.
*   The output is a single binary blob: `[12-byte IV] + [16-byte GCM Tag] + [Ciphertext]`.
*   This blob is what gets uploaded to Google Drive or the backend.

---

## 🛠️ 5. Technology Stack Summary

*   **Core Backend:** Python 3.11, FastAPI (REST + WebSockets).
*   **Database:** SQLite (Async via `aiosqlite`), SQLAlchemy 2.0 ORM.
*   **Cryptography:** 
    *   Python: `PyCryptodome`, `argon2-cffi`.
    *   Dart: `pointycastle`, `encrypt`.
    *   ECC: Custom implementation of Galois Arithmetic and Reed-Solomon.
*   **Frontend UI/UX:** Flutter 3.x, Google Fonts, dynamic animated builders.
*   **State Management:** `flutter_bloc` (Events, States, Transitions).
*   **Cloud API:** `googleapis`, `google_sign_in`.

---

## 🎓 6. Academic Value & Conclusion
SecureCorrect successfully bridges the gap between **Abstract Algebra (Galois Fields)**, **Information Theory (Error Correcting Codes)**, and **Modern Cybersecurity (Zero-Knowledge Architectures)**. 

By pushing the boundaries of authentication logic, this project demonstrates that highly secure cryptographic systems do not have to inherently sacrifice user experience. It provides a robust framework that is forgiving of human error while remaining mathematically resilient against cryptographic attacks.
