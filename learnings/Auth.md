# 🔐 Auth System Walkthrough — Registration, Login & JWT Tokens

## What We Built

A complete **user authentication system** for the Cortex backend that lets users:
1. **Register** — create a new account with email, display name, and password
2. **Login** — prove who they are and get back a **JWT token**

The JWT is like a wristband at a concert — once you get it at the door (login), you flash it to get into any area (protected routes) without going back to the door every time. We built the "door" today; tomorrow we'll build the wristband-checking.

---

## Commands Run

| # | Command | What It Did |
|---|---------|-------------|
| 1 | `python -c "import secrets; print(secrets.token_hex(32))"` | Generated a random 64-char hex string for JWT signing |
| 2 | `pip install passlib[bcrypt] python-jose[cryptography]` | Installed password hashing + JWT libraries |
| 3 | `pip install email-validator` | Installed email format validation (needed by Pydantic's `EmailStr`) |

---

## Files Changed & Created

### Overview

| File | Action | Purpose |
|------|--------|---------|
| [.env](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/.env) | Modified | Added JWT secret + algorithm + expiry settings |
| [.env.example](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/.env.example) | Modified | Added JWT key names (no real secrets) for other devs |
| [requirements.txt](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/requirements.txt) | Modified | Added 3 new packages |
| [config.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/core/config.py) | Modified | Load JWT settings from .env |
| [security.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/core/security.py) | **Created** | Password hashing + JWT creation utilities |
| [user.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/models/user.py) | Modified | Added `password_hash` column |
| [auth.py (schemas)](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/schemas/auth.py) | **Created** | Request/response validation models |
| [auth.py (routes)](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/api/routes/auth.py) | **Created** | Register + Login API endpoints |
| [main.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/main.py) | Modified | Wired auth router into the app |

---

## Deep Explanation — File by File

### 1. `.env` — Your Secret Vault

```
JWT_SECRET_KEY=85ebdc86a820f67bdc50458236979f7d31a54de276220ed4f6eb410f4ad7b67e
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

**What are these?**

- **JWT_SECRET_KEY** — A long random string that acts like a master password. When we create a JWT, we "sign" it with this key. When we later verify a JWT, we check it with the same key. If anyone changes even one character in the token, the signature won't match and we'll reject it. **This must stay secret** — if someone gets it, they can forge tokens pretending to be any user.

- **JWT_ALGORITHM** — `HS256` means "HMAC using SHA-256". In plain English: it's the mathematical recipe for signing the token. HS256 is *symmetric* — the same key signs and verifies. (Asymmetric algorithms like RS256 use a separate public/private key pair, but that's overkill for us.)

- **JWT_EXPIRE_MINUTES** — Tokens die after 60 minutes. This limits damage if a token gets stolen — the thief only has an hour, not forever.

**Why `.env` and not hardcoded?**
Because `.env` is in `.gitignore` — it never gets committed to Git. The real secret stays on your machine (or your production server). The `.env.example` file has just the key *names*, so other developers know what to fill in.

---

### 2. `requirements.txt` — New Dependencies

```
passlib[bcrypt]          ← password hashing
python-jose[cryptography] ← JWT creation/verification  
email-validator          ← Pydantic's EmailStr needs this
```

**Why passlib, not just bcrypt directly?**
passlib is a *wrapper* that manages hashing algorithms for you. If you ever want to switch from bcrypt to argon2 (a newer algorithm), you change one line in passlib's config and it handles the transition — even auto-upgrading old hashes when users log in.

**Why python-jose, not PyJWT?**
Both work. python-jose supports more algorithms and has a consistent API. The `[cryptography]` extra uses Python's robust `cryptography` library under the hood instead of a pure-Python implementation.

---

### 3. [config.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/core/config.py) — Loading JWT Settings

```diff
+    JWT_SECRET_KEY: str                # loaded from .env, no default = required
+    JWT_ALGORITHM: str = "HS256"       # HMAC-SHA256 (symmetric signing)  
+    JWT_EXPIRE_MINUTES: int = 60       # token lifetime in minutes
```

**How does this work?**
`pydantic-settings` automatically reads these from `.env`. The `Settings` class is like a contract: "I need these values, and they must be these types." If `JWT_SECRET_KEY` is missing from `.env`, the app *won't start* — it crashes immediately with a clear error. This is intentional: better to fail loudly at startup than silently run without security.

`JWT_SECRET_KEY: str` has no default → **required**. `JWT_ALGORITHM: str = "HS256"` has a default → optional in `.env`.

---

### 4. [security.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/core/security.py) — The Crypto Brain

Three small functions that do all the security work:

#### `hash_password("MySecret123")` → `"$2b$12$LJ3m4ys1Kn..."`

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

**What happens inside:**
1. bcrypt generates a random **salt** (random string mixed into the hash)
2. It hashes `"MySecret123"` + salt together, running through 2^12 = 4096 rounds of computation
3. The result `"$2b$12$..."` embeds the algorithm (`$2b$`), cost factor (`$12$`), salt, and hash all in one string

**Why bcrypt instead of SHA-256 or MD5?**
SHA-256 and MD5 are *fast* — a GPU can compute billions per second. That means an attacker can try billions of password guesses per second. bcrypt is *intentionally slow* (~100ms per hash). Trying 10 billion passwords would take ~31 years. That's the whole point.

#### `verify_password("MySecret123", "$2b$12$LJ3m4ys1Kn...")` → `True`

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

**How can it verify if hashing is one-way?**
The stored hash `"$2b$12$LJ3m4ys1Kn..."` contains the salt that was used. bcrypt extracts the salt, hashes the incoming password with that *same* salt, and compares the result. If they match → correct password. No need to "decrypt" anything.

#### `create_access_token({"sub": "user-uuid"})` → `"eyJhbGciOi..."`

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```

**What's a JWT? (JSON Web Token)**

A JWT has three parts separated by dots: `header.payload.signature`

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImV4cCI6MTcxOH0.aBcDeFgH...
|_______header_______|  |____________payload______________|  |__signature__|
```

1. **Header** — `{"alg": "HS256"}` (Base64-encoded) — tells you *how* it was signed
2. **Payload** — `{"sub": "user-123", "exp": 1718...}` (Base64-encoded) — the actual data
3. **Signature** — HMAC-SHA256(header + "." + payload, SECRET_KEY) — proves nobody tampered with it

> [!IMPORTANT]
> JWTs are **signed, not encrypted**. Anyone can decode the payload (it's just Base64). The signature only proves it wasn't modified. Never put passwords or sensitive data in a JWT.

---

### 5. [user.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/models/user.py) — New Column

```diff
+    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
```

This adds a `password_hash` column to the `users` table. After you run the Alembic migration, your table will look like:

| Column | Type | Example |
|--------|------|---------|
| id | UUID | `550e8400-e29b-41d4-a716-...` |
| email | VARCHAR(255) | `user@example.com` |
| display_name | VARCHAR(100) | `Pranav` |
| **password_hash** | **VARCHAR(255)** | `$2b$12$LJ3m4ys1Kn...` |
| created_at | TIMESTAMP | `2026-07-28 14:30:00+05:30` |

---

### 6. [auth.py (schemas)](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/schemas/auth.py) — Data Shapes

These are **Pydantic models** — think of them as "forms" that validate data:

```
UserRegister  → "To register, give me: email, password, display_name"
UserLogin     → "To log in, give me: email, password"
UserResponse  → "After registering, I'll give you: id, email, display_name, created_at" 
TokenResponse → "After logging in, I'll give you: access_token, token_type"
```

**Why `EmailStr` instead of plain `str`?**
`EmailStr` automatically validates email format. Send `"not-an-email"` and Pydantic rejects it *before your code even runs* — with a clear error message. One line of code, free validation.

**Why `UserResponse` has no `password_hash`?**
This is a critical security pattern: the response schema acts as a *filter*. Even though the SQLAlchemy `User` object has `password_hash`, Pydantic only serializes the fields defined in `UserResponse`. The hash never leaves the server.

**What's `model_config = {"from_attributes": True}`?**
Normally Pydantic expects dictionaries. This setting lets it read directly from SQLAlchemy model objects (which use attributes like `user.email` instead of `user["email"]`). Without this, `UserResponse.model_validate(user_orm_object)` would crash.

---

### 7. [auth.py (routes)](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/api/routes/auth.py) — The Endpoints

#### `POST /auth/register` — Creating an Account

```
Client sends: {"email": "a@b.com", "password": "secret", "display_name": "Pranav"}
                            ↓
Step 1: Check if email exists in DB  ──→ Yes? Return 400 "already exists"
                            ↓ No
Step 2: hash_password("secret")  →  "$2b$12$..."
                            ↓  
Step 3: INSERT INTO users (email, display_name, password_hash) VALUES (...)
                            ↓
Step 4: Return {"id": "...", "email": "a@b.com", "display_name": "Pranav", "created_at": "..."}
                          (notice: NO password in the response!)
```

#### `POST /auth/login` — Getting a Token

```
Client sends: {"email": "a@b.com", "password": "secret"}
                            ↓
Step 1: SELECT * FROM users WHERE email = 'a@b.com'  ──→ Not found? Return 401
                            ↓ Found
Step 2: verify_password("secret", user.password_hash)  ──→ Doesn't match? Return 401
                            ↓ Matches!
Step 3: create_access_token({"sub": "user-uuid"})  →  "eyJhbG..."
                            ↓
Step 4: Return {"access_token": "eyJhbG...", "token_type": "bearer"}
```

**Why return the same "Invalid email or password" for both wrong email AND wrong password?**
Security! If we said "email not found" vs "wrong password", an attacker could figure out which emails are registered in our system (called "user enumeration"). By always giving the same vague error, we reveal nothing.

**What's `Depends(get_db)`?**
FastAPI's dependency injection. It's saying: "Before running this endpoint, call `get_db()` to get a database session, and pass it to me as the `db` parameter. When the request is done, clean it up automatically." This means we never have to worry about opening/closing database connections — FastAPI handles it.

---

### 8. [main.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/main.py) — Wiring It In

```python
from app.api.routes.auth import router as auth_router
app.include_router(auth_router)
```

This tells FastAPI: "Hey, there's a new group of endpoints in `auth_router`. Add them to the app." Since the router has `prefix="/auth"`, all its routes automatically get `/auth/` prepended — so `@router.post("/register")` becomes `POST /auth/register`.

---

## The Big Picture — How Everything Connects

```
Client (browser/Postman)
    │
    │  POST /auth/register  {"email": "...", "password": "..."}
    ▼
┌──────────┐
│ main.py  │  ← FastAPI receives the request
│          │  ← Routes it to auth_router
└────┬─────┘
     ▼
┌──────────────────┐
│ routes/auth.py   │  ← register() function runs
│                  │  ← Pydantic validates the body using schemas/auth.py
└────┬─────────────┘
     │ Calls hash_password()
     ▼
┌──────────────────┐
│ core/security.py │  ← bcrypt hashes the password
└────┬─────────────┘
     │ Returns hash
     ▼
┌──────────────────┐
│ models/user.py   │  ← New User object created with the hash
│ + db/session.py  │  ← SQLAlchemy writes it to PostgreSQL
└────┬─────────────┘
     │ Returns user object
     ▼
┌──────────────────┐
│ schemas/auth.py  │  ← UserResponse filters out password_hash
│ (UserResponse)   │  ← Only sends safe fields back
└──────────────────┘
     │
     ▼
Client receives: {"id": "...", "email": "...", "display_name": "...", "created_at": "..."}
```

---

## Your Turn — Run the Migration

Since you added a new column (`password_hash`) to the User model, the database doesn't know about it yet. You need to tell Alembic to generate a migration and apply it.

Run these commands **in the backend directory** with your venv activated:

### Command 1: Generate the migration file
```bash
alembic revision --autogenerate -m "add password_hash to users"
```
This compares your SQLAlchemy models (code) against the live database and generates a Python file describing the difference: "add column `password_hash` to table `users`".

### Command 2: Apply the migration
```bash
alembic upgrade head
```
This runs the migration file, actually executing the `ALTER TABLE users ADD COLUMN password_hash ...` SQL on your PostgreSQL database.

> [!WARNING]
> If you have existing rows in the `users` table (from earlier testing), this migration will fail because `password_hash` is `NOT NULL` and existing rows don't have a value. Two options:
> 1. **Easiest**: Delete existing rows first: `DELETE FROM users;` in psql
> 2. **Better**: Edit the generated migration file to add `server_default=""` to the `add_column` call, then remove it after

### Command 3: Start the server
```bash
uvicorn app.main:app --reload
```

### Command 4: Test via Swagger
Open `http://localhost:8000/docs` in your browser and try:
1. **Register** → `POST /auth/register` with body `{"email": "test@example.com", "password": "MySecret123", "display_name": "Pranav"}`
2. **Verify in DB** → `SELECT email, password_hash FROM users;` — should show a bcrypt hash
3. **Login (correct)** → `POST /auth/login` with `{"email": "test@example.com", "password": "MySecret123"}` → should get a JWT back
4. **Login (wrong password)** → same email but `"password": "wrong"` → should get 401
5. **Duplicate register** → try registering the same email again → should get 400
