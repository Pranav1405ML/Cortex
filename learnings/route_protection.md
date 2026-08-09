# 🛡️ Route Protection — How `get_current_user` Works

## The Problem We're Solving

In the previous phase, we built login — a user sends their email + password, and we give them back a JWT token. Great.

But that token is useless right now. No route actually **checks** it. It's like handing out concert wristbands at the door but having zero security guards inside the venue — anyone can walk into any area, wristband or not.

We need a way to say: *"This route requires a valid token. If you don't have one, go away."*

### The Naive (Bad) Approach

You might think: "I'll just add token-checking code to every route function."

```python
# ❌ DON'T DO THIS — copy-pasting the same logic everywhere
@router.get("/my-conversations")
async def my_conversations(request: Request, db = Depends(get_db)):
    # Extract token from header
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "No token")
    token = token.replace("Bearer ", "")
    
    # Verify JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Bad token")
    
    # Look up user
    user = await db.execute(select(User).where(User.id == payload["sub"]))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    
    # NOW finally do the actual work...
    conversations = await db.execute(
        select(Conversation).where(Conversation.user_id == user.id)
    )
    return conversations.scalars().all()
```

If you have 20 protected routes, you'd copy-paste those 15 lines of token-checking code 20 times. That's:
- **Error-prone** — change one copy, forget the others
- **Ugly** — half your route is boilerplate, not business logic
- **Hard to maintain** — what if you change how tokens work?

### The Smart Approach: A Dependency

Instead, we extract all that token-checking logic into **one reusable function** called `get_current_user`. Then any route that needs protection just writes:

```python
# ✅ DO THIS — one line, and you're protected
@router.get("/my-conversations")
async def my_conversations(
    current_user: User = Depends(get_current_user),  # ← this is the magic line
    db = Depends(get_db),
):
    # current_user is already verified and loaded from the DB!
    # If the token was bad, we'd never even reach this line.
    conversations = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id)
    )
    return conversations.scalars().all()
```

**One line** replaces 15 lines of boilerplate. Write the checking logic once, use it everywhere.

---

## What Is a "Dependency" in FastAPI?

You've already used one: `get_db`.

```python
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
```

When FastAPI sees `Depends(get_db)`, it thinks:

> *"Before running `login()`, I need to call `get_db()` first, get its return value, and pass it as the `db` parameter."*

That's all a dependency is — **a function that runs before your route, and whose return value gets injected as a parameter.** FastAPI handles calling it, passing the result, and cleaning up afterward.

`get_current_user` works exactly the same way:

```python
async def get_me(current_user: User = Depends(get_current_user)):
```

> *"Before running `get_me()`, call `get_current_user()` first. If it returns a User, pass it as `current_user`. If it raises an exception, stop — don't even run `get_me()`."*

### Dependencies Can Depend on Other Dependencies

Here's where it gets powerful. `get_current_user` itself has dependencies:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),   # ← dependency #1: extract token from header
    db: AsyncSession = Depends(get_db),     # ← dependency #2: get a DB session
) -> User:
```

So when a route uses `Depends(get_current_user)`, FastAPI builds a **chain**:

```
Your route needs → get_current_user
                     which needs → oauth2_scheme (extracts token from header)
                     which needs → get_db (opens a database session)
```

FastAPI resolves this chain automatically, bottom-up. You don't call any of these functions yourself — FastAPI does it all for you.

---

## The Three Pieces We Built

### Piece 1: `decode_access_token()` in security.py

In the previous phase we built `create_access_token()` — it takes data and **encodes** it into a JWT. Now we need the reverse: take a JWT and **decode** it back into data.

```python
# security.py

def create_access_token(data: dict) -> str:
    """Encode: dict → JWT string"""
    # ... adds expiry, signs with secret key ...
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Decode: JWT string → dict (or raises JWTError)"""
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
```

**Think of it like a lockbox:**
- `create_access_token` = put a note in the box and lock it with your key
- `decode_access_token` = unlock the box with the same key and read the note

If someone **tampered** with the token (changed a character), the signature won't match → `JWTError`.
If the token is **expired** (past its `exp` time), `jwt.decode` catches that too → `JWTError`.

**One important detail:** notice `algorithm` (singular) in encode vs `algorithms` (plural, a list) in decode. That's just how the `python-jose` library works — when decoding, you provide a list of algorithms you're willing to accept. We only accept `["HS256"]`.

---

### Piece 2: `OAuth2PasswordBearer` — The Header Extractor

Before `get_current_user` can verify a token, something needs to **pull the token out of the request header**. That's what `OAuth2PasswordBearer` does.

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
```

**What does this object do?**

When a client makes a request to a protected route, they send the token in a header like this:

```
GET /auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

`OAuth2PasswordBearer` automatically:
1. Looks for the `Authorization` header
2. Strips off the `"Bearer "` prefix
3. Gives you just the token string: `"eyJhbGciOiJIUzI1NiIs..."`
4. If the header is missing → immediately returns `401 Unauthorized` (your code never even runs)

**Bonus:** It also adds a 🔒 **"Authorize" button** to the Swagger `/docs` page. When you click it, you can paste your token, and all subsequent requests from the Swagger UI will include the `Authorization: Bearer <token>` header automatically. Super handy for testing.

**What's `tokenUrl="/auth/login"`?**
This only affects the Swagger UI — it tells the docs page *"the endpoint for getting a token is `/auth/login`"*. It has zero effect on your actual backend code. It's purely a hint for the documentation page.

---

### Piece 3: `get_current_user()` — The Actual Dependency

This is the main function that ties everything together. Let's walk through it step by step:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),   # Step 0: extract token from header
    db: AsyncSession = Depends(get_db),     # Step 0: get a DB session
) -> User:
```

**Step 0** happens before `get_current_user` even starts. FastAPI calls `oauth2_scheme` to get the token, and `get_db` to get a database session. Then it passes both into `get_current_user`.

```python
    # --- Step 1: Decode and verify the JWT ---
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

**Step 1:** Try to decode the JWT. If it's garbage, expired, or tampered with, `decode_access_token` raises `JWTError`. We catch it and convert it to a clean 401 response.

**What's `headers={"WWW-Authenticate": "Bearer"}`?**
This is an HTTP standard thing. When you reject a request with 401, you're supposed to include a `WWW-Authenticate` header that tells the client *how* to authenticate. `"Bearer"` means "send me a Bearer token." Browsers and HTTP libraries can use this hint. It's optional but follows the spec properly.

```python
    # --- Step 2: Extract the user ID from the token ---
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

**Step 2:** The decoded payload looks like `{"sub": "f11ccd73-25e5-4dc7-...", "exp": 1722...}`. We grab the `"sub"` (subject) field — that's where we stored the user's UUID during login (remember `create_access_token(data={"sub": str(user.id)})`). If somehow there's no `"sub"` field, the token is malformed → 401.

```python
    # --- Step 3: Look up the user in the database ---
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id_str))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
```

**Step 3:** We have the user's UUID from the token. Now look them up in the database. Why? Because:
- The user might have been **deleted** since the token was issued
- We need the **full User object** (email, display_name, etc.) to use in the route

If the user exists → return the `User` object. If not → 401.

---

## How It All Connects — The Full Chain

When a request hits `GET /auth/me`, here's what happens, step by step:

```
Client sends:
  GET /auth/me
  Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

         │
         ▼
┌─────────────────────────────────────────────┐
│  FastAPI sees: Depends(get_current_user)     │
│  "I need to run get_current_user first"      │
└─────────┬───────────────────────────────────┘
          │
          │  But get_current_user has its own dependencies...
          ▼
┌─────────────────────────────────────────────┐
│  Depends(oauth2_scheme)                      │
│  → Extracts "eyJhbGci..." from the header    │
│  → Passes it as the `token` parameter        │
└─────────┬───────────────────────────────────┘
          │
┌─────────────────────────────────────────────┐
│  Depends(get_db)                             │
│  → Opens a database session                  │
│  → Passes it as the `db` parameter           │
└─────────┬───────────────────────────────────┘
          │
          │  Now get_current_user runs with both:
          ▼
┌─────────────────────────────────────────────┐
│  get_current_user(token, db)                 │
│                                              │
│  1. decode_access_token(token)               │
│     → Verifies signature ✓                   │
│     → Checks not expired ✓                   │
│     → Returns {"sub": "f11ccd73...", ...}    │
│                                              │
│  2. payload.get("sub") → "f11ccd73..."       │
│                                              │
│  3. SELECT * FROM users WHERE id = 'f11c..'  │
│     → Found! Returns the User object         │
└─────────┬───────────────────────────────────┘
          │
          │  get_current_user returns the User object
          ▼
┌─────────────────────────────────────────────┐
│  get_me(current_user=User(...))              │
│                                              │
│  → UserResponse.model_validate(current_user) │
│  → Returns: {id, email, display_name, ...}   │
└─────────────────────────────────────────────┘
          │
          ▼
Client receives:
  {
    "id": "f11ccd73-25e5-4dc7-...",
    "email": "pranav@gmail.com",
    "display_name": "pranav",
    "created_at": "2026-07-29T..."
  }
```

**And if the token is missing, invalid, or expired?**

```
Client sends:
  GET /auth/me
  (no Authorization header)

         │
         ▼
  oauth2_scheme → "No Authorization header found!"
                → Returns 401 Unauthorized IMMEDIATELY
                → get_current_user never runs
                → get_me() never runs
                → Client gets: {"detail": "Not authenticated"}
```

The route function body (`get_me`) never executes. FastAPI short-circuits at the dependency level.

---

## The `/auth/me` Test Route

This route is intentionally simple — it exists purely to prove the mechanism works:

```python
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
```

That's it. One line of actual logic. The entire security check is handled by `Depends(get_current_user)`.

**How to use this pattern in future routes:**

Any route that needs to know "who is making this request?" just adds the same parameter:

```python
@router.get("/my-conversations")
async def my_conversations(
    current_user: User = Depends(get_current_user),  # ← add this
    db: AsyncSession = Depends(get_db),
):
    # current_user.id is the authenticated user's ID
    # Use it to filter data: "only show ME my conversations"
    conversations = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id)
    )
    return conversations.scalars().all()
```

---

## Quick Reference — What Lives Where

| File | What It Does | Analogy |
|------|-------------|---------|
| `core/security.py` | `decode_access_token()` — verifies + decodes JWT | The lock mechanism |
| `api/dependencies.py` | `get_current_user()` — the reusable auth check | The security guard |
| `api/dependencies.py` | `oauth2_scheme` — extracts token from header | The guard checking your wristband |
| `api/routes/auth.py` | `GET /auth/me` — a protected route | A VIP area with a guard at the door |

---

## Testing Checklist

In `/docs` (http://localhost:8000/docs):

1. **No token:** Try `GET /auth/me` without authorizing → should get `401`
2. **Get a token:** Call `POST /auth/login` with valid credentials → copy the `access_token`
3. **Authorize:** Click the 🔒 button at the top of Swagger → paste the token → click "Authorize"
4. **Valid token:** Try `GET /auth/me` again → should get your user info back
5. **Bad token:** Click 🔒 again → replace with `this.is.garbage` → try `GET /auth/me` → should get `401`

---

## Key Takeaways

1. **Dependencies are functions that run before your route.** `Depends(get_db)` gives you a database session. `Depends(get_current_user)` gives you the authenticated user. Same pattern, different use case.

2. **Dependencies can chain.** `get_current_user` depends on `oauth2_scheme` AND `get_db`. FastAPI resolves the whole chain for you automatically.

3. **If a dependency raises an exception, the route never runs.** This is how protection works — `get_current_user` raises 401 before your route body even starts executing.

4. **Write once, use everywhere.** Any route that needs auth adds one parameter: `current_user: User = Depends(get_current_user)`. No copy-pasting.

5. **`OAuth2PasswordBearer` is just a header extractor** — it pulls the token from `Authorization: Bearer <token>`. It also adds the 🔒 button to Swagger for free.

6. **`decode_access_token` is the reverse of `create_access_token`** — one encodes data into a JWT, the other decodes a JWT back into data (while verifying it hasn't been tampered with).
