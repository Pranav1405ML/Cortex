# Database Models & Alembic — A Beginner's Guide

Everything in `backend/app/models/` and `backend/alembic/`, explained from scratch.

---

## Table of Contents

1. [The Problem We're Solving](#1-the-problem-were-solving)
2. [What is an ORM?](#2-what-is-an-orm)
3. [The Base Class — Where It All Starts](#3-the-base-class--where-it-all-starts)
4. [Understanding a Model File Line by Line](#4-understanding-a-model-file-line-by-line)
   - [The Imports](#the-imports)
   - [The Class & Table Name](#the-class--table-name)
   - [Columns Deep Dive](#columns-deep-dive)
   - [Relationships Deep Dive](#relationships-deep-dive)
5. [All Three Models — The Full Picture](#5-all-three-models--the-full-picture)
6. [The `__init__.py` File — Why It Matters](#6-the-__init__py-file--why-it-matters)
7. [The `db/session.py` File — Connecting to PostgreSQL](#7-the-dbsessionpy-file--connecting-to-postgresql)
8. [Alembic — Git for Your Database](#8-alembic--git-for-your-database)
   - [What is Alembic?](#what-is-alembic)
   - [Why Can't We Just Use the Models Directly?](#why-cant-we-just-use-the-models-directly)
   - [How Alembic Works — The Mental Model](#how-alembic-works--the-mental-model)
   - [The Alembic Files Explained](#the-alembic-files-explained)
   - [The Migration File Explained](#the-migration-file-explained)
   - [Alembic Commands You'll Use](#alembic-commands-youll-use)
   - [A Real Scenario — Adding a Column Later](#a-real-scenario--adding-a-column-later)

---

## 1. The Problem We're Solving

Without an ORM, talking to a database looks like this:

```python
# Raw SQL — you're writing SQL strings inside Python
cursor.execute("""
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        display_name VARCHAR(100) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
""")

# Inserting a user — manually constructing SQL
cursor.execute(
    "INSERT INTO users (id, email, display_name) VALUES (%s, %s, %s)",
    (some_uuid, "pranav@gmail.com", "Pranav")
)

# The result comes back as a raw tuple — no structure
row = cursor.fetchone()
email = row[1]  # What's index 1? You have to remember.
```

**Problems with this:**
- SQL strings have no autocomplete, no type checking, no IDE support
- Easy to make typos (`VARCAHR` instead of `VARCHAR`) and you only find out at runtime
- You have to manually remember column positions (is email index 1 or 2?)
- Database-specific SQL (PostgreSQL vs MySQL vs SQLite all have differences)

---

## 2. What is an ORM?

**ORM = Object-Relational Mapper.** It maps Python classes to database tables.

| Python (ORM)              | Database (SQL)              |
|---------------------------|-----------------------------|
| A **class** (`User`)      | A **table** (`users`)       |
| A class **attribute** (`email`) | A table **column** (`email`) |
| An **instance** (`User(email="a@b.com")`) | A **row** in the table |

With SQLAlchemy (our ORM), the same code becomes:

```python
# Define the table as a Python class
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)

# Insert a user — just create a Python object
user = User(email="pranav@gmail.com", display_name="Pranav")
session.add(user)
await session.commit()

# Read a user — get back a proper Python object
user = await session.get(User, some_uuid)
print(user.email)  # IDE knows this is a string, gives autocomplete
```

**You write Python. SQLAlchemy writes the SQL for you.**

---

## 3. The Base Class — Where It All Starts

**File: `app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

This is the simplest file in the project. Here's what it does:

- `DeclarativeBase` is SQLAlchemy's parent class for all models
- Any class that inherits from `Base` becomes a database table
- `Base` internally keeps a **registry** (`Base.metadata`) of all tables — this is how Alembic knows what tables exist

Think of it like this:

```
Base (knows about all tables)
 ├── User        → "users" table
 ├── Conversation → "conversations" table
 └── Message     → "messages" table
```

When you write `class User(Base)`, User automatically registers itself with `Base.metadata`. Later, Alembic reads `Base.metadata` to figure out what tables to create.

**This file is boilerplate. You write it once and never touch it.**

---

## 4. Understanding a Model File Line by Line

Let's use `user.py` as the example since it's the simplest.

### The Imports

```python
from __future__ import annotations          # ①
import uuid                                  # ②
from datetime import datetime                # ③
from typing import TYPE_CHECKING             # ④
from sqlalchemy import String, DateTime, func  # ⑤
from sqlalchemy.dialects.postgresql import UUID  # ⑥
from sqlalchemy.orm import Mapped, mapped_column, relationship  # ⑦
from app.db.base import Base                 # ⑧

if TYPE_CHECKING:                            # ⑨
    from app.models.conversation import Conversation
```

Let's break each one down:

| # | Import | What it is | Why we need it |
|---|--------|------------|----------------|
| ① | `from __future__ import annotations` | Makes all type hints lazy (treated as strings, not evaluated at runtime) | Prevents circular import crashes. User references Conversation, Conversation references User — without this, Python would crash trying to import both at the same time |
| ② | `uuid` | Python's built-in UUID library | We use UUIDs as primary keys instead of auto-incrementing integers |
| ③ | `datetime` | Python's date/time library | For the `created_at` column's type hint |
| ④ | `TYPE_CHECKING` | A constant that's `True` in your editor, `False` at runtime | Used in ⑨ to import Conversation *only* for the type checker |
| ⑤ | `String, DateTime, func` | SQLAlchemy column types and functions | `String(255)` = varchar, `DateTime` = timestamp, `func.now()` = SQL's `NOW()` function |
| ⑥ | `UUID` | PostgreSQL-specific UUID type | PostgreSQL has a native UUID column type — this uses it |
| ⑦ | `Mapped, mapped_column, relationship` | SQLAlchemy's modern ORM tools | `Mapped` = type annotation, `mapped_column` = column definition, `relationship` = table linking |
| ⑧ | `Base` | Our base class from `db/base.py` | Every model inherits from this |
| ⑨ | `if TYPE_CHECKING:` block | Conditional import | Imports `Conversation` **only** when Pyright/your editor is checking types. At runtime, this code **never runs**. This solves the circular import problem |

#### The Circular Import Problem (Why ① and ⑨ Exist)

```
user.py imports Conversation (for the relationship type hint)
conversation.py imports User (for the relationship type hint)
```

If both files try to import each other normally, Python gets stuck in an infinite loop:
1. Python starts loading `user.py`
2. `user.py` says `from conversation import Conversation`
3. Python starts loading `conversation.py`
4. `conversation.py` says `from user import User`
5. Python tries to go back to `user.py`, but it's not done loading yet → 💥 crash

**Solution:**
- `from __future__ import annotations` — makes Python treat type hints as strings, so it doesn't try to actually load the class
- `if TYPE_CHECKING:` — the import only happens when your editor is analyzing the code, never when Python actually runs it

### The Class & Table Name

```python
class User(Base):
    __tablename__ = "users"
```

- `class User(Base)` — "User is a database table" (because it inherits from Base)
- `__tablename__ = "users"` — the actual table name in PostgreSQL. Convention: class name is singular (`User`), table name is plural (`users`)

### Columns Deep Dive

Each line defines one column in the database table:

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
)
```

Let's decode this pattern: **`name: Mapped[PythonType] = mapped_column(SQLType, ...options)`**

| Part | What it means |
|------|---------------|
| `id` | Column name in Python (also becomes the column name in the DB) |
| `Mapped[uuid.UUID]` | "In Python, this value is a `uuid.UUID` object" — gives your editor type checking |
| `UUID(as_uuid=True)` | "In PostgreSQL, store this as a UUID column" — `as_uuid=True` means convert to/from Python UUID objects automatically |
| `primary_key=True` | This column uniquely identifies each row. Every table needs exactly one primary key |
| `default=uuid.uuid4` | When you create a new `User()` without specifying an id, Python auto-generates a random UUID |

Here's every column in User, decoded:

```python
# Column: id
# SQL type: UUID (a 128-bit unique identifier)
# Constraints: PRIMARY KEY (every row must have a unique id)
# Default: auto-generated random UUID
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
)

# Column: email
# SQL type: VARCHAR(255) (a string with max 255 characters)
# Constraints: UNIQUE (no two users can share an email), NOT NULL (can't be empty)
email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

# Column: display_name
# SQL type: VARCHAR(100)
# Constraints: NOT NULL
display_name: Mapped[str] = mapped_column(String(100), nullable=False)

# Column: created_at
# SQL type: TIMESTAMP WITH TIME ZONE
# Default: server_default=func.now() means PostgreSQL fills this in
#          automatically when a row is inserted. You don't set it in Python.
# Note: "server_default" vs "default":
#   - server_default → PostgreSQL handles it (the DB writes NOW())
#   - default → Python handles it (Python generates the value before sending to DB)
#   For timestamps, server_default is better because the DB clock is the
#   single source of truth.
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
)
```

#### Common Column Options Cheat Sheet

| Option | What it does | Example |
|--------|-------------|---------|
| `primary_key=True` | This column is the unique identifier | Every table needs one |
| `nullable=False` | Column can't be NULL (empty) | An email must always exist |
| `unique=True` | No two rows can have the same value | No duplicate emails |
| `default=value` | Python fills this in if you don't provide it | `default=uuid.uuid4` |
| `server_default=expr` | The **database** fills this in | `server_default=func.now()` |
| `ForeignKey("table.col")` | This column references another table | Links conversations to users |
| `ondelete="CASCADE"` | If the referenced row is deleted, delete this row too | Delete user → delete their conversations |

#### SQL Types We Use

| SQLAlchemy Type | PostgreSQL Type | Python Type | When to use |
|-----------------|-----------------|-------------|-------------|
| `UUID(as_uuid=True)` | `UUID` | `uuid.UUID` | Primary keys, unique identifiers |
| `String(255)` | `VARCHAR(255)` | `str` | Short text with a max length (emails, names, titles) |
| `Text` | `TEXT` | `str` | Long text with no length limit (message content, descriptions) |
| `DateTime(timezone=True)` | `TIMESTAMPTZ` | `datetime` | Timestamps (when something was created/updated) |

### Relationships Deep Dive

Relationships are the most confusing part, so let's go slow.

```python
# In user.py
conversations: Mapped[list["Conversation"]] = relationship(
    back_populates="user", cascade="all, delete-orphan"
)
```

**This does NOT create a database column.** It creates a Python-only convenience attribute.

Think of it as a shortcut. Without it:
```python
# To get all conversations for a user, you'd write:
conversations = await session.execute(
    select(Conversation).where(Conversation.user_id == user.id)
)
```

With it:
```python
# Just access the attribute directly:
user.conversations  # → list of Conversation objects
```

#### How Relationships Link Together

Relationships always come in **pairs**. Each side knows about the other via `back_populates`:

```
USER SIDE (user.py):                    CONVERSATION SIDE (conversation.py):
                                        
conversations = relationship(           user = relationship(
    back_populates="user"      ←→          back_populates="conversations"
)                                       )
```

- `back_populates="user"` in User says: "Conversation has an attribute called `.user` that points back to me"
- `back_populates="conversations"` in Conversation says: "User has an attribute called `.conversations` that points back to me"

They MUST match. If you rename one, you must rename the other.

#### Relationship vs ForeignKey — What's the Difference?

```python
# THIS creates an actual database column (a real column called "user_id" in the conversations table)
user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
)

# THIS does NOT create a column — it's a Python-only shortcut
user: Mapped["User"] = relationship(back_populates="conversations")
```

| | ForeignKey | Relationship |
|---|---|---|
| Creates a DB column? | ✅ Yes | ❌ No |
| Exists in PostgreSQL? | ✅ Yes | ❌ No (Python only) |
| What it stores | The actual `id` value (a UUID) | The full Python object |
| Required? | Yes, for linking tables | No, but very convenient |
| Example value | `"550e8400-e29b-..."` | `<User object>` |

#### The `cascade` Option

```python
conversations: Mapped[list["Conversation"]] = relationship(
    back_populates="user", cascade="all, delete-orphan"
)
```

`cascade="all, delete-orphan"` means:
- If you **delete a User in Python** (using `session.delete(user)`), SQLAlchemy will also delete all their Conversations
- "delete-orphan" means: if a Conversation's `.user` is set to `None`, delete that Conversation (it's an "orphan" — it lost its parent)

> **Note:** This is the **Python/ORM-level** cascade. There's also the **database-level** cascade (`ondelete="CASCADE"` on the ForeignKey), which does the same thing but inside PostgreSQL itself. We use both for safety — even if someone deletes a row with raw SQL (bypassing Python), the cascade still works.

---

## 5. All Three Models — The Full Picture

Here's how the three tables relate:

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────────┐
│    USERS     │         │  CONVERSATIONS   │         │    MESSAGES      │
├──────────────┤    1:N  ├──────────────────┤    1:N  ├──────────────────┤
│ id (PK)      │◄───────┤│ id (PK)          │◄───────┤│ id (PK)          │
│ email        │        ││ title            │        ││ conversation_id  │──► FK to conversations.id
│ display_name │        ││ user_id          │──► FK  ││ role             │
│ created_at   │        ││ created_at       │        ││ content          │
└──────────────┘        │└──────────────────┘        ││ created_at       │
                        │                            │└──────────────────┘
                        │                            │
                   "A user has                  "A conversation has
                    many conversations"          many messages"
```

**1:N** means "one-to-many":
- One User → Many Conversations
- One Conversation → Many Messages

The "many" side always holds the ForeignKey. Conversations hold `user_id`, Messages hold `conversation_id`.

#### What Each Table Stores (in Plain English)

| Table | Purpose | Real-world example |
|-------|---------|-------------------|
| `users` | People who use Cortex | You, with your email and display name |
| `conversations` | Chat sessions | "Help me learn Python" — a thread of messages |
| `messages` | Individual messages in a conversation | User: "What is a list?" / Assistant: "A list is..." |

---

## 6. The `__init__.py` File — Why It Matters

**File: `app/models/__init__.py`**

```python
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message

__all__ = ["User", "Conversation", "Message"]
```

This file does two things:

**1. Convenience imports:**
```python
# Without __init__.py, you'd write:
from app.models.user import User
from app.models.conversation import Conversation

# With __init__.py, you can write:
from app.models import User, Conversation
```

**2. (Critical) Registers models with Base.metadata:**
When Python executes `from app.models.user import User`, it loads `user.py`, which defines `class User(Base)`. That act of defining the class registers it with `Base.metadata`. Alembic reads `Base.metadata` to know what tables to create.

If you create a new model file but forget to import it here, **Alembic won't see it** and won't generate a migration for it.

---

## 7. The `db/session.py` File — Connecting to PostgreSQL

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
```

### The Engine

```python
engine = create_async_engine(settings.DATABASE_URL, echo=True)
```

The **engine** is the lowest-level connection to PostgreSQL. It manages a **connection pool** — a set of pre-opened connections that get reused.

Why a pool? Opening a new database connection is slow (~50ms). If every API request opened a fresh connection, your app would be sluggish. The pool keeps a few connections alive and hands them out as needed.

`echo=True` prints every SQL query to the console. Super helpful for learning. You'll see things like:
```
INFO sqlalchemy.engine.Engine SELECT users.id, users.email FROM users WHERE users.id = $1
INFO sqlalchemy.engine.Engine [generated in 0.00029s] ('550e8400-...',)
```

### The Session Factory

```python
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

A **session** is a short-lived "conversation" with the database. You:
1. Open a session
2. Do some reads/writes
3. Commit (save changes) or rollback (undo changes)
4. Close the session

The **session factory** is a function that creates new sessions. Think of it like a cookie cutter — you call it each time you need a fresh session.

`expire_on_commit=False` → after you `commit()`, you can still read object attributes without the session hitting the database again. Without this, accessing `user.email` after a commit would trigger another SQL query.

### The `get_db()` Dependency

```python
async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
```

This is a **FastAPI dependency**. You don't call it yourself — FastAPI calls it for you. Later, when we write endpoints, you'll use it like:

```python
@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    # `db` is a session — ready to use
    # FastAPI opened it for you, and will close it when the request ends
    result = await db.execute(select(User))
    return result.scalars().all()
```

`yield` is the key. Everything before `yield` runs at the **start** of the request (opens the session). Everything after `yield` runs at the **end** (closes the session). `async with` ensures the session is always properly closed, even if an error occurs.

---

## 8. Alembic — Git for Your Database

### What is Alembic?

**Alembic is a database migration tool.** It tracks changes to your database schema over time.

Think of it this way:
- **Git** tracks changes to your **code** files
- **Alembic** tracks changes to your **database tables**

Without Alembic, if you add a column to a model, you'd have to:
1. Write `ALTER TABLE users ADD COLUMN bio TEXT;` yourself
2. Run it manually on your local DB
3. Remember to run it on the production DB later
4. Hope you didn't forget any steps

With Alembic, you:
1. Change your Python model
2. Run one command — Alembic figures out what changed and generates the SQL
3. Run another command — Alembic applies it
4. The migration file gets committed to git, so everyone on the team (and production) can apply the same change

### Why Can't We Just Use the Models Directly?

Good question. SQLAlchemy has a `Base.metadata.create_all(engine)` function that creates all tables from scratch. Why not just use that?

**Because it only creates — it never updates.**

- `create_all()` → "Create these tables if they don't exist." If they already exist? It does nothing.
- Need to add a column? `create_all()` can't help. You need `ALTER TABLE`.
- Need to rename a column? Same problem.
- Need to undo a change? Impossible without migrations.

Alembic solves all of this by generating **migration files** — step-by-step instructions for evolving your database.

### How Alembic Works — The Mental Model

```
┌─────────────────────┐     ┌─────────────────────┐
│  YOUR PYTHON CODE   │     │  YOUR LIVE DATABASE  │
│  (Base.metadata)    │     │  (PostgreSQL tables)  │
│                     │     │                       │
│  User               │     │  users ✅             │
│  Conversation       │     │  conversations ✅     │
│  Message            │     │  messages ✅          │
│  NEW: SearchResult  │     │  (nothing new)        │
└─────────┬───────────┘     └───────────┬───────────┘
          │                             │
          └──────────┬──────────────────┘
                     │
              Alembic compares
              these two sides
                     │
                     ▼
          ┌─────────────────────┐
          │   MIGRATION FILE    │
          │                     │
          │  def upgrade():     │
          │    create_table(    │
          │      "search_results" │
          │    )                │
          │                    │
          │  def downgrade():  │
          │    drop_table(     │
          │      "search_results" │
          │    )                │
          └─────────────────────┘
```

**Step 1: `alembic revision --autogenerate -m "description"`**
- Alembic reads your Python models (`Base.metadata`)
- Alembic connects to PostgreSQL and reads the current tables
- It compares the two and figures out the difference
- It generates a migration file with `upgrade()` (apply the change) and `downgrade()` (undo the change)

**Step 2: `alembic upgrade head`**
- Alembic runs the `upgrade()` function, which executes the SQL on your database
- It records which migration was applied (in a special `alembic_version` table)

### The Alembic Files Explained

```
backend/
├── alembic.ini                    ← Config file (boilerplate)
└── alembic/
    ├── env.py                     ← The brain (boilerplate, but important to understand)
    ├── script.py.mako             ← Template for new migration files (never touch)
    ├── README                     ← Auto-generated readme (ignore)
    └── versions/
        └── 5ef1b29bc5c7_create_users...py  ← Our first migration!
```

#### `alembic.ini` — Configuration (Boilerplate)

The only line that matters:
```ini
sqlalchemy.url =
```
We left this blank because we set the URL from Python code instead (in `env.py`). This way the URL comes from `.env` — one source of truth.

**You'll never edit this file again.**

#### `alembic/env.py` — The Brain (Boilerplate, but worth understanding)

This file tells Alembic three things:

**1. Where's the database?**
```python
from app.core.config import settings
config.set_main_option(
    "sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%")
)
```
It grabs `DATABASE_URL` from your `.env` via the Settings class. The `.replace("%", "%%")` is because Alembic's config parser treats `%` as special (like `%(here)s`), so we escape it.

**2. What do the models look like?**
```python
from app.db.base import Base
import app.models  # This import is CRITICAL

target_metadata = Base.metadata
```
`target_metadata` is what Alembic compares against the live database. `Base.metadata` knows about every model that inherits from `Base`. The `import app.models` line forces Python to load all model files, which registers them with `Base.metadata`.

**3. How to connect? (Async)**
```python
async def run_async_migrations():
    connectable = async_engine_from_config(...)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```
Since we use `asyncpg` (an async PostgreSQL driver), we need an async engine. The regular Alembic setup uses sync connections, so we override it.

**You'll rarely edit this file.** Only if you add a second database or change drivers.

#### `script.py.mako` — Migration Template (Never Touch)

This is the template that Alembic uses when generating new migration files. It's like a cookie cutter. When you run `alembic revision --autogenerate`, Alembic fills in this template with the detected changes.

**Never edit this.**

### The Migration File Explained

**File: `alembic/versions/5ef1b29bc5c7_create_users_conversations_messages.py`**

This is the file Alembic auto-generated when we ran `alembic revision --autogenerate`.

```python
# These identifiers form a linked list of migrations
revision: str = '5ef1b29bc5c7'        # This migration's unique ID
down_revision = None                   # Previous migration (None = this is the first)
```

Think of migrations as a chain:
```
None → 5ef1b29bc5c7 → (next migration) → (next) → ...
         ↑ we are here
```

Each migration knows its predecessor (`down_revision`). Alembic follows this chain to figure out which migrations have been applied and which haven't.

#### The `upgrade()` function — "Apply this change"

```python
def upgrade() -> None:
    # Creates the "users" table with all its columns
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Creates "conversations" (after users, because it has a FK to users)
    op.create_table('conversations', ...)
    
    # Creates "messages" (after conversations, because it has a FK to conversations)
    op.create_table('messages', ...)
```

Notice the order matters: `users` first, then `conversations` (which references `users.id`), then `messages` (which references `conversations.id`). You can't create a foreign key to a table that doesn't exist yet.

#### The `downgrade()` function — "Undo this change"

```python
def downgrade() -> None:
    op.drop_table('messages')       # Drop messages first (it depends on conversations)
    op.drop_table('conversations')  # Then conversations (depends on users)
    op.drop_table('users')          # Then users (no dependencies)
```

Reverse order! You can't drop `users` while `conversations` still has a foreign key pointing to it.

#### How `alembic_version` Works

When you run `alembic upgrade head`, Alembic creates a special table called `alembic_version` in your database:

```
alembic_version table:
┌──────────────────┐
│ version_num      │
├──────────────────┤
│ 5ef1b29bc5c7     │  ← "this database has applied migration 5ef1b29bc5c7"
└──────────────────┘
```

Next time you run `alembic upgrade head`, it checks this table, sees `5ef1b29bc5c7` is already applied, and skips it. It only runs NEW migrations.

### Alembic Commands You'll Use

There are really only 4 commands you need to know:

```bash
# 1. GENERATE a new migration (after changing models)
alembic revision --autogenerate -m "describe what changed"
# Example: alembic revision --autogenerate -m "add bio column to users"

# 2. APPLY all pending migrations
alembic upgrade head
# "head" means "latest migration". This applies everything that hasn't been applied yet.

# 3. SEE what migration you're currently on
alembic current
# Shows the current revision ID

# 4. UNDO the last migration
alembic downgrade -1
# Runs the downgrade() function of the last applied migration
# Use this if you messed up and want to rollback
```

### A Real Scenario — Adding a Column Later

Let's say next week you want to add a `bio` field to the User model.

**Step 1: Edit the model**
```python
# In user.py, add this new column:
bio: Mapped[str | None] = mapped_column(Text, nullable=True)
```
(`str | None` and `nullable=True` means this column is optional — existing users won't have a bio)

**Step 2: Generate the migration**
```bash
alembic revision --autogenerate -m "add bio column to users"
```

Alembic will generate something like:
```python
def upgrade():
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('users', 'bio')
```

**Step 3: Apply it**
```bash
alembic upgrade head
```

Done. The `users` table now has a `bio` column. The migration file is committed to git, so any teammate (or production server) can run `alembic upgrade head` to get the same change.

---

## Quick Reference — File Purpose Summary

| File | Purpose | Boilerplate? |
|------|---------|-------------|
| `db/base.py` | Defines `Base` — the parent class for all models | ✅ Yes, never touch |
| `db/session.py` | Creates the engine (connection) and session factory | Mostly — only change `echo` setting |
| `models/__init__.py` | Imports all models (registers them with Base) | ⚠️ Update when adding new models |
| `models/user.py` | Defines the `users` table | ❌ You'll edit this as the schema evolves |
| `models/conversation.py` | Defines the `conversations` table | ❌ Same |
| `models/message.py` | Defines the `messages` table | ❌ Same |
| `alembic.ini` | Alembic config | ✅ Yes, never touch |
| `alembic/env.py` | Tells Alembic how to connect and what models exist | ✅ Yes, rarely touch |
| `alembic/script.py.mako` | Template for migration files | ✅ Yes, never touch |
| `alembic/versions/*.py` | Auto-generated migration files | ⚠️ Review after generation, but don't write from scratch |
