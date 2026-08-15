# Conversations & Messages — Full Walkthrough

## What Was Built

We added the ability for authenticated users to **create, view, list, and delete conversations**, and to **add/list messages** within those conversations. This is the core chat functionality layer of your AI search engine.

## Why We Need This

Your app already had:
- **User model** + auth (register/login/JWT)
- **Conversation model** + **Message model** (SQLAlchemy ORM classes in `models/`)

But models alone just define the *shape* of the database tables. They don't do anything by themselves. What was missing was the **operational code** — the layers that actually read/write data and expose HTTP endpoints. That's what we built.

---

## The Three Layers (and why they're separate)

### Layer 1: CRUD — "Talk to the database"

| File | Purpose |
|------|---------|
| [conversation.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/crud/conversation.py) | `create`, `get`, `list`, `delete` conversations |
| [message.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/crud/message.py) | `create`, `list` messages |

**Why a separate CRUD layer?** Because database queries should be reusable. Tomorrow, when you build the AI search pipeline, it will need to create messages too — but it won't go through an HTTP route. By isolating the database logic, any part of your app can use it.

#### The critical design decision: `get_conversation(db, conversation_id, user_id)`

This function filters by **both** `id` AND `user_id` in the same SQL query:

```python
select(Conversation).where(
    Conversation.id == conversation_id,
    Conversation.user_id == user_id,     # ← ownership check baked in
)
```

This means:
- Conversation doesn't exist → returns `None`
- Conversation exists but belongs to someone else → **also** returns `None`

The caller (the route) can't tell the difference — it just sees `None` and returns 404. This is **intentional security**: an attacker can't probe whether a conversation ID is valid or not.

> [!IMPORTANT]
> The alternative (query by id alone, then check `if conv.user_id != current_user.id`) is a common security antipattern. It leaks information: a 403 tells the attacker "this ID exists, you just can't access it". Our approach always returns the same 404.

---

### Layer 2: Schemas — "Shape of the HTTP request/response"

| File | Purpose |
|------|---------|
| [conversation.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/schemas/conversation.py) | `ConversationCreate` (input) + `ConversationResponse` (output) |
| [message.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/schemas/message.py) | `MessageCreate` (input) + `MessageResponse` (output) |

**Why separate schemas from models?** They solve different problems:
- **Models** = what the database stores (includes `password_hash`, internal fields, etc.)
- **Schemas** = what the API accepts/returns (never expose sensitive internal data)

For example, `ConversationResponse` has `id`, `title`, `user_id`, `created_at` — but the underlying `Conversation` model also has the ORM relationship fields. Pydantic schemas act as a **security filter** on what leaves your API.

`model_config = {"from_attributes": True}` tells Pydantic: "you can build this from a SQLAlchemy ORM object, not just a dictionary." This is what makes `ConversationResponse.model_validate(conversation_orm_object)` work.

---

### Layer 3: Routes — "HTTP endpoints"

[conversations.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/api/routes/conversations.py)

| Method | Path | What it does |
|--------|------|-------------|
| `POST` | `/conversations` | Create a new conversation |
| `GET` | `/conversations` | List current user's conversations |
| `GET` | `/conversations/{id}` | Get one (404 if not yours) |
| `DELETE` | `/conversations/{id}` | Delete one (404 if not yours) |
| `POST` | `/conversations/{id}/messages` | Add a message |
| `GET` | `/conversations/{id}/messages` | List messages |

**Every route** requires `current_user: User = Depends(get_current_user)` — so unauthenticated requests get 401 before any logic runs.

The `_get_owned_conversation()` helper avoids repeating the ownership check in every route. It calls the CRUD `get_conversation()` (which filters by user_id) and raises 404 if the result is `None`.

---

### Layer 4: Registration in main.py

[main.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/main.py) — just 2 lines added:

```diff
+from app.api.routes.conversations import router as conversations_router
 ...
+app.include_router(conversations_router)
```

Without this, FastAPI doesn't know the routes exist.

---

## Git Status

```
Modified:   app/main.py                        (2 lines added)
New:        app/api/routes/conversations.py     (routes)
New:        app/crud/__init__.py                (empty, makes it a package)
New:        app/crud/conversation.py            (CRUD functions)
New:        app/crud/message.py                 (CRUD functions)
New:        app/schemas/conversation.py         (Pydantic schemas)
New:        app/schemas/message.py              (Pydantic schemas)
```

---

## Manual Verification Steps

Start the server first:
```powershell
cd d:\Projects\Personal projects\AI_Search_Engine\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Then open a **second terminal** and run these commands one by one. Each step builds on the previous.

### Step 1 — Register two users

```powershell
# User A (Alice)
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"alice@test.com","password":"pass123","display_name":"Alice"}'

# User B (Bob)
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"bob@test.com","password":"pass456","display_name":"Bob"}'
```

### Step 2 — Login as User A, save the token

```powershell
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"alice@test.com","password":"pass123"}'
```

Copy the `access_token` value from the response. Save it:
```powershell
$TOKEN_A = "paste_alice_token_here"
```

### Step 3 — User A creates a conversation

```powershell
curl -X POST http://localhost:8000/conversations -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN_A" -d '{"title":"Alice Private Chat"}'
```

✅ Should return **201** with a JSON body containing `id`, `title`, `user_id`, `created_at`.
**Copy the `id` value** — you'll need it next.

```powershell
$CONV_ID = "paste_conversation_id_here"
```

### Step 4 — User A can access their conversation

```powershell
# Get single conversation
curl http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_A"

# List all conversations
curl http://localhost:8000/conversations -H "Authorization: Bearer $TOKEN_A"
```

✅ Both should return **200** with Alice's conversation data.

### Step 5 — User A adds messages

```powershell
curl -X POST http://localhost:8000/conversations/$CONV_ID/messages -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN_A" -d '{"role":"user","content":"Hello assistant!"}'

curl -X POST http://localhost:8000/conversations/$CONV_ID/messages -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN_A" -d '{"role":"assistant","content":"Hello! How can I help?"}'
```

✅ Both should return **201**.

```powershell
# List messages
curl http://localhost:8000/conversations/$CONV_ID/messages -H "Authorization: Bearer $TOKEN_A"
```

✅ Should return **200** with 2 messages in chronological order.

### Step 6 — Login as User B

```powershell
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"bob@test.com","password":"pass456"}'
```

```powershell
$TOKEN_B = "paste_bob_token_here"
```

### Step 7 — 🔒 THE OWNERSHIP BOUNDARY TEST

This is the most important part. **All of these must return 404:**

```powershell
# Bob tries to GET Alice's conversation
curl http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_B"

# Bob tries to add a message to Alice's conversation
curl -X POST http://localhost:8000/conversations/$CONV_ID/messages -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN_B" -d '{"role":"user","content":"Hacking attempt!"}'

# Bob tries to read Alice's messages
curl http://localhost:8000/conversations/$CONV_ID/messages -H "Authorization: Bearer $TOKEN_B"

# Bob tries to delete Alice's conversation
curl -X DELETE http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_B"
```

✅ **All four must return `{"detail":"Conversation not found."}` with status 404.**

❌ If any return 200 or the actual data — the ownership boundary is broken.

### Step 8 — Bob's list is empty

```powershell
curl http://localhost:8000/conversations -H "Authorization: Bearer $TOKEN_B"
```

✅ Should return **200** with an empty list `[]`.

### Step 9 — Alice can still access everything

```powershell
curl http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_A"
```

✅ Should still return **200** — Bob's failed attempts didn't affect Alice's data.

### Step 10 — Alice deletes her conversation

```powershell
curl -X DELETE http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_A"
```

✅ Should return **204 No Content** (empty response body).

```powershell
# Confirm it's gone
curl http://localhost:8000/conversations/$CONV_ID -H "Authorization: Bearer $TOKEN_A"
```

✅ Should now return **404**.

### Step 11 — No auth = 401

```powershell
# Try without any token
curl http://localhost:8000/conversations
```

✅ Should return **401 Unauthorized** — proves the auth dependency works.

---

> [!TIP]
> You can also test all of this interactively at **http://localhost:8000/docs** — the Swagger UI has an "Authorize" button where you paste the JWT, then you can click through each endpoint.
