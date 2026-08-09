"""
schemas/auth.py — Pydantic Models for Authentication

These are NOT database models — they're "shapes" that FastAPI uses to:
  1. Validate incoming request data (e.g., "does the login body have an email?")
  2. Serialize outgoing response data (e.g., "only send back these fields")
  3. Auto-generate the Swagger /docs UI

Think of them as contracts:
  - "If you want to register, you MUST send email + password + display_name"
  - "When you log in successfully, you'll get back an access_token + token_type"
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# REQUEST schemas — what the client sends TO us
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    """
    Sent in the body of POST /auth/register.

    EmailStr is a pydantic type that validates email format automatically —
    so "not-an-email" will be rejected before our code even runs.
    """
    email: EmailStr
    password: str
    display_name: str


class UserLogin(BaseModel):
    """
    Sent in the body of POST /auth/login.
    Just email + password — that's all you need to prove who you are.
    """
    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# RESPONSE schemas — what we send BACK to the client
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Returned after successful registration.

    IMPORTANT: Notice there's NO password or password_hash field here.
    This is intentional — we NEVER send password data back to the client.
    Pydantic will simply ignore any extra fields from the User ORM object.

    model_config with from_attributes=True tells Pydantic:
    "You can create this from a SQLAlchemy model object, not just a dict."
    So we can do: UserResponse.model_validate(user_orm_object)
    """
    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    Returned after successful login.

    This follows the OAuth2 convention:
      - access_token: the JWT string itself
      - token_type: always "bearer" (means "whoever bears/carries this token
        is authenticated" — it's sent in the Authorization header like:
        Authorization: Bearer eyJhbGciOi...)
    """
    access_token: str
    token_type: str = "bearer"
