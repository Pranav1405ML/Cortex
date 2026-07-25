# Python Async Concepts — Explained Simply

Let's break down every concept in the `session.py` file, building from the ground up.

---

## 1. `async` / `await` — "Don't just stand there, do something else"

### The Problem
Imagine you're a waiter at a restaurant. A customer orders food. You go to the kitchen, hand the order to the chef, and then... **you just stand there staring at the chef** until the food is ready. Meanwhile 10 other customers are waiting to order. That's **synchronous** code.

### The Solution
`async`/`await` lets you say: "Hey chef, I'll come back when it's ready. Let me go take other orders."

```python
# SYNCHRONOUS (blocking) — waiter stands and waits
def get_user():
    user = db.query("SELECT * FROM users WHERE id = 1")  # ⏳ blocks here
    return user                                            # nothing else can happen

# ASYNCHRONOUS (non-blocking) — waiter goes and does other things
async def get_user():
    user = await db.query("SELECT * FROM users WHERE id = 1")  # ⏳ goes do other work
    return user                                                 # comes back when ready
```

### The Rules
- `async def` means: "This function **might** need to wait for something"
- `await` means: "**Wait here**, but let other tasks run while I wait"
- You can only use `await` **inside** an `async def` function

### Why does this matter for your app?
Your FastAPI server handles many users at once. If one user's database query takes 200ms, you don't want the entire server frozen for 200ms. `async`/`await` lets the server handle other requests while waiting for that query.

---

## 2. `yield` — "Give something out, then come back"

### `return` vs `yield`
```python
# return: gives a value and THE FUNCTION IS DONE. Gone. Dead. Finished.
def get_number():
    return 42
    # function is completely finished here, memory cleaned up

# yield: gives a value but THE FUNCTION IS PAUSED. Still alive. Waiting.
def get_numbers():
    yield 1    # gives 1, then pauses ⏸️
    yield 2    # when asked again, gives 2, then pauses ⏸️
    yield 3    # when asked again, gives 3, then done
```

### Why is `yield` useful?

The key insight: **code runs AFTER the yield too**. This means you can do setup → yield → cleanup:

```python
def open_file():
    f = open("data.txt")    # 1️⃣ SETUP: open the file
    yield f                  # 2️⃣ PAUSE: hand the file to whoever asked
    f.close()                # 3️⃣ CLEANUP: close the file when they're done
```

This is exactly what your `get_db()` does! It:
1. **Opens** a database session
2. **Yields** it (hands it to your route function)
3. **Closes** it when the route function finishes

---

## 3. Context Managers — "Auto-cleanup"

### The Problem
```python
file = open("data.txt")
data = file.read()
# Oh no, what if an error happens here? ❌
# file.close() never gets called!
# The file stays open, leaking resources 😱
file.close()
```

### The Solution: `with` statement
```python
with open("data.txt") as file:
    data = file.read()
# File is AUTOMATICALLY closed here, even if an error happened ✅
```

`with` is a **context manager**. It guarantees:
1. Something is **set up** when you enter the block
2. Something is **cleaned up** when you leave the block (even if there's an error)

### `async with` — same thing, but async

```python
# Regular context manager
with open("file.txt") as f:
    data = f.read()

# Async context manager — for things that need await (like DB connections)
async with async_session_factory() as session:
    # session is open and ready here
    pass
# session is automatically closed here ✅
```

You need `async with` instead of `with` because opening/closing a database connection is an I/O operation that should be non-blocking.

---

## 4. Putting it all together — the `get_db()` function

Now let's read the actual code with fresh eyes:

```python
async def get_db() -> AsyncGenerator[AsyncSession]:

    async with async_session_factory() as session:
        yield session
```

Here's what happens, step by step, when a request hits the API:

```
1. FastAPI calls get_db()

2. async with async_session_factory() as session:
   → Opens a database connection/session (SETUP)

3. yield session
   → Hands the session to your route function (PAUSE)
   → Your route function runs and does its database queries

4. When the route function finishes (or crashes)...
   → The "async with" block exits
   → The session is automatically closed (CLEANUP)
```

### Visualized:

```
    get_db()                          Your Route Function
    ────────                          ──────────────────
    Open session ──────┐
                       │
    yield session ─────┼──→  receives session
         ⏸️ paused      │     does db queries
                       │     returns response
    ←──────────────────┘
    Close session ✅
```

---

## 5. `AsyncSession` vs `AsyncGenerator`

### `AsyncSession`
This is SQLAlchemy's async database session object. It's the thing you use to talk to the database:

```python
async def create_user(session: AsyncSession):
    user = User(email="test@test.com", display_name="Test")
    session.add(user)          # stage the new user
    await session.commit()     # save to database
```

It's like a **conversation with the database** — you open it, send queries, and close it.

### `AsyncGenerator`
This is just the **type annotation** describing what `get_db()` is:

```python
# This says: "get_db is an async generator that YIELDS AsyncSession objects"
async def get_db() -> AsyncGenerator[AsyncSession]:
```

Remember — because `get_db()` uses `yield` (not `return`), it's a **generator**, not a regular function. So its type isn't `AsyncSession` (that's what it *yields*), it's `AsyncGenerator[AsyncSession]` (that's what it *is*).

Think of it like this:

| Analogy | Type | What it gives you |
|---|---|---|
| A hen | `Generator[Egg]` | Eggs |
| A hen is NOT an egg | ~~`Egg`~~ | ❌ Wrong type |

The function *is* a generator. It *yields* sessions. The type describes the function, not what it yields.

---

## 6. Why does FastAPI use this pattern?

FastAPI has a **dependency injection** system. When you write:

```python
@app.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    # db is a ready-to-use database session here
    ...
```

FastAPI sees `Depends(get_db)` and does this:
1. Calls `get_db()`
2. Gets the yielded `session`
3. Passes it to your route function as `db`
4. When the route finishes → the generator resumes → session closes

This way, **you never have to manually open or close database sessions**. FastAPI handles it for you through the `yield` + context manager pattern.

---

## Quick Reference

| Concept | One-liner |
|---|---|
| `async def` | "This function might wait for I/O" |
| `await` | "Wait here, but let others work meanwhile" |
| `yield` | "Give this out, pause, then resume later" |
| `with` / `async with` | "Auto-setup and auto-cleanup" |
| `AsyncSession` | "A conversation with the database" |
| `AsyncGenerator` | "A type that describes a function using yield" |
| `Depends(get_db)` | "FastAPI, please call get_db() and give me the session" |
