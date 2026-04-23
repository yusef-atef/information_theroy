# SecureCorrect

> **Fault-Tolerant Cloud Storage with Reed-Solomon Error-Correcting Authentication**

SecureCorrect lets users log in with minor password typos — even forgotten characters — by applying Reed-Solomon Error-Correcting Codes at the authentication layer before key derivation.

---

## Project Structure

```
project/
├── backend/
│   ├── ecc/
│   │   ├── galois_field.py      # GF(256) arithmetic
│   │   ├── reed_solomon.py      # RS encoder + syndrome decoder
│   │   ├── mapping_engine.py    # Per-user ASCII → GF(256) mapping
│   │   └── ecc_auth.py          # register_password / verify_and_correct
│   ├── routers/
│   │   ├── auth.py              # POST /auth/register, /auth/login, /auth/me
│   │   └── files.py             # POST /files/upload, GET /files/list, etc.
│   ├── main.py                  # FastAPI app entry point
│   ├── models.py                # SQLAlchemy ORM (User, File)
│   ├── schemas.py               # Pydantic v2 schemas
│   ├── security.py              # Argon2 + AES-256-GCM + HMAC + JWT
│   ├── storage.py               # Firebase Storage abstraction
│   ├── database.py              # Async SQLAlchemy engine
│   ├── requirements.txt
│   └── tests/
│       └── test_ecc.py          # Full unit + integration test suite
├── frontend/
│   └── lib/
│       ├── main.dart
│       ├── app.dart             # Theme + routing
│       ├── core/                # API client, secure storage, models
│       ├── features/
│       │   ├── auth/            # Login + Register screens + BLoC
│       │   └── vault/           # Vault screen + File card + BLoC
│       └── widgets/             # EccPasswordField, GradientButton
└── Dockerfile
```

---

## Quick Start

### Backend

```bash
cd project
pip install -r backend/requirements.txt

# Dev server
uvicorn backend.main:app --reload

# Run tests
pytest backend/tests/ -v
```

Set environment variables before production deploy:
```
SECRET_KEY=<32+ random bytes>
MASTER_KEY=<exactly 32 bytes>
FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

### Flutter

```bash
cd project/frontend
flutter pub get
flutter run
```

---

## ECC Correction Capacity

| Input | Capacity |
|---|---|
| Pure errors (wrong chars) | Up to **2** |
| Pure erasures (`*` wildcards) | Up to **4** |
| Mixed (`2e + r ≤ 4`) | e.g. 1 error + 2 wildcards |

---

## Security Properties

| Threat | Defence |
|---|---|
| Rainbow Table | Per-user randomized GF(256) mapping |
| False-positive correction | Argon2 hash integrity guard |
| File tampering | AES-256-GCM authentication tag + HMAC-SHA256 |
| Token theft | 15-min JWT access tokens + refresh rotation |
| Mapping table leak | AES-256-GCM encrypted at rest (server master key) |
