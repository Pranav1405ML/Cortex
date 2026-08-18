# AI Integration — Full Walkthrough

## What Was Built

We connected our backend to **Google's Gemini AI**. Now when a user sends a message, the backend:
1. Saves the user's message in the database
2. Sends the **entire conversation history** to Gemini
3. Gets back an AI-generated reply
4. Saves that reply as an `assistant` message
5. Returns both messages to the client

This is the moment Cortex goes from a "chat storage app" to an actual AI assistant.

---

## The Big Picture: What Changed

| File | What it does |
|------|-------------|
| [requirements.txt](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/requirements.txt) | Added `google-genai` — Google's official Python SDK for Gemini |
| [config.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/core/config.py) | Added `GEMINI_API_KEY` to Settings |
| [services/__init__.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/services/__init__.py) | New package — external service integrations |
| [services/ai_service.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/services/ai_service.py) | The Gemini integration — `generate_reply()` function |
| [conversations.py](file:///d:/Projects/Personal%20projects/AI_Search_Engine/backend/app/api/routes/conversations.py) | Updated `POST /messages` to call Gemini and return the AI reply |

---

## New Architectural Layer: `services/`

Before this, we had:

```
routes/     → HTTP endpoints (what the client talks to)
schemas/    → Request/response shapes (validation)
crud/       → Database operations (what talks to PostgreSQL)
```

Now we added:

```
services/   → External system integrations (what talks to the outside world)
```

**Why not put the Gemini code in `crud/`?** Because `crud/` is for database operations — it uses SQLAlchemy, it talks to PostgreSQL. Gemini is a completely different system (an HTTP API to Google's servers). Mixing them would violate the single-responsibility principle.

**Why not put it directly in the route?** Because routes should be thin orchestrators — they wire things together but don't contain heavy business logic. If we ever swap Gemini for Claude or GPT, we change **one file** (`ai_service.py`), not the route.

> [!TIP]
> Think of it this way:
> - `crud/` = talks to **our** database
> - `services/` = talks to **other people's** APIs
> - `routes/` = orchestrates both

---

## The SDK: `google-genai`

This is Google's **official Python SDK** for the Gemini API. Key things to know:

### Installation
```bash
pip install google-genai
```

### Sync vs Async

The SDK has both sync and async clients. Since our entire backend is async (FastAPI + SQLAlchemy async), we use the async version:

```python
from google import genai

client = genai.Client(api_key="your-key")

# Sync (DON'T use in FastAPI — it blocks the event loop):
response = client.models.generate_content(...)

# Async (what we use):
response = await client.aio.models.generate_content(...)
```

The magic is `client.aio` — it gives you the async interface. Same client, same API key, just add `.aio` to access the async methods.

> [!IMPORTANT]
> If you use the sync version in FastAPI, your entire server blocks while waiting for Gemini to respond. That means **no other requests can be handled** during that time. Always use `client.aio` in async frameworks.

---

## Role Mapping: A Real Integration Detail

This is something you'll hit with every LLM API — they all name things slightly differently.

| Our database | Gemini expects |
|-------------|----------------|
| `role="user"` | `role="user"` ✅ Same |
| `role="assistant"` | `role="model"` ⚠️ Different! |

So we translate when building the request:

```python
for msg in conversation_history:
    gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
```

If you ever integrate with OpenAI, they use `"assistant"` (like us). Anthropic uses `"assistant"` too. Gemini is the odd one out with `"model"`. This translation layer is exactly why we keep the integration in its own file.

---

## Message Format: How Gemini Wants Its Input

Gemini doesn't just want a list of strings. It wants structured `Content` objects with `Part` objects inside:

```python
from google.genai import types

# Each message becomes this structure:
types.Content(
    role="user",                              # or "model"
    parts=[types.Part(text="Hello!")],        # the actual text
)
```

The `contents` parameter to `generate_content` is a **list** of these `Content` objects — the full conversation history, in chronological order.

### System Instructions

Gemini handles system prompts separately from the conversation. You pass them in the `config`:

```python
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=gemini_contents,          # the conversation history
    config=types.GenerateContentConfig(
        system_instruction="You are Cortex, a helpful AI assistant.",
    ),
)
```

> [!NOTE]
> Some LLM APIs (like OpenAI) put the system message as the first item in the messages list with `role="system"`. Gemini uses a separate `system_instruction` field instead. Same concept, different API design.

---

## Error Handling: The Custom Exception Pattern

This is arguably the most important design decision in this feature.

### The Problem

When Gemini fails (bad API key, rate limit, their servers are down), the SDK throws exceptions like `genai_errors.ClientError` or `genai_errors.ServerError`. If we let these bubble up raw:

1. The client gets a **500 Internal Server Error** with a Python traceback
2. The traceback might **leak sensitive info** (API key, internal paths)
3. The client can't tell if **our** server crashed or if the **upstream** service failed

### The Solution: `AIServiceError`

We created a custom exception class:

```python
class AIServiceError(Exception):
    def __init__(self, detail: str = "AI service unavailable.", status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
```

It carries two things:
- `detail` — a clean, human-readable message (safe to show to clients)
- `status_code` — always `502 Bad Gateway`

### Why 502 and not 500?

| Code | Meaning |
|------|---------|
| `500 Internal Server Error` | **Our** code crashed — a bug in our server |
| `502 Bad Gateway` | We tried to call another service and **it** failed |

502 tells the client: "Our server is fine, but something we depend on is broken." This is the semantically correct status code when an upstream API fails.

### The Catch Chain

In `ai_service.py`, we wrap errors from most specific to most general:

```python
try:
    # ... call Gemini ...
except AIServiceError:
    raise                           # 1. Don't re-wrap our own errors

except genai_errors.ClientError:    # 2. Bad key, rate limit (4xx from Google)
    raise AIServiceError(detail="AI service request failed (client error).")

except genai_errors.ServerError:    # 3. Gemini's servers are down (5xx)
    raise AIServiceError(detail="AI service is temporarily unavailable.")

except Exception:                   # 4. Network timeout, DNS failure, anything else
    raise AIServiceError(detail="AI service encountered an unexpected error.")
```

Then in the **route**, catching is simple:

```python
try:
    reply_text = await generate_reply(history)
except AIServiceError as exc:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)
```

> [!IMPORTANT]
> The `from exc` syntax in `raise AIServiceError(...) from exc` preserves the original exception in the **server logs** (for debugging) while the client only sees our clean message. You get the best of both worlds.

---

## The Updated Route Flow

Here's what `POST /conversations/{id}/messages` does now, step by step:

```
Client sends: {"role": "user", "content": "Hello!"}
         │
         ▼
   ① Ownership check (does this conversation belong to you?)
         │ No → 404
         ▼
   ② Store user message in DB via crud
         │
         ▼
   ③ Fetch ALL messages for this conversation (chronological)
         │
         ▼
   ④ Call generate_reply(history)
         │     │
         │     ├─ Maps roles: "assistant" → "model"
         │     ├─ Builds Content objects
         │     ├─ Sends to Gemini with system instruction
         │     └─ Returns the reply text
         │
         │ Failed? → 502 with clean error
         ▼
   ⑤ Store assistant reply in DB via crud
         │
         ▼
   ⑥ Return [user_message, assistant_message] as JSON
```

Two important design choices here:

1. **The user message is saved BEFORE calling Gemini.** If Gemini fails, the user's message is still in the database. They don't lose what they typed.

2. **We fetch the FULL history every time.** This is how Gemini gets multi-turn context. It's stateless — it doesn't remember previous calls. We have to send everything each time.

> [!WARNING]
> Sending full history means token costs grow with conversation length. Right now this is fine (free tier, short conversations). Later, you might want to truncate old messages or summarize them to stay within token limits.

---

## The Response Shape Changed

Before this change, `POST /messages` returned **one** message:
```json
{"id": "...", "role": "user", "content": "Hello!", ...}
```

Now it returns a **list of two** messages:
```json
[
  {"id": "...", "role": "user", "content": "Hello!", ...},
  {"id": "...", "role": "assistant", "content": "Hi! I'm Cortex...", ...}
]
```

The `response_model` changed from `MessageResponse` to `list[MessageResponse]`. This means any frontend code consuming this endpoint needs to expect an array now.

---

## Config: Loading the API Key

We added one line to `Settings`:

```python
GEMINI_API_KEY: str    # loaded from .env, no default = required
```

No default value means **the app won't start** if the key is missing from `.env`. This is intentional — you want to fail fast at startup, not discover the key is missing when a user tries to chat.

This follows the same pattern as `JWT_SECRET_KEY` — required secrets have no defaults.

---

## Key Takeaways

1. **Separate concerns by who you're talking to.** `crud/` → database. `services/` → external APIs. `routes/` → orchestration.

2. **Never let third-party errors leak to clients.** Wrap them in your own exception type with clean messages and appropriate status codes.

3. **502 ≠ 500.** Use the right status code — it tells clients (and monitoring tools) whether the problem is yours or someone else's.

4. **Async all the way.** In an async framework, use async SDK methods. One blocking call can stall your entire server.

5. **Role mapping is a real concern.** Every LLM API names things differently. Keep the translation in one place.

6. **Save user input before calling external services.** If the external service fails, the user shouldn't lose their message.
