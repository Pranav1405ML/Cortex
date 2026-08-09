"""
api/dependencies.py — Shared FastAPI Dependencies

Dependencies are reusable functions that FastAPI runs BEFORE your route.
You've already used one: get_db() provides a database session.

This file adds get_current_user() — a dependency that:
  1. Extracts the JWT from the Authorization header
  2. Verifies it's valid (not expired, not tampered with)
  3. Looks up the user in the database
  4. Returns the User object (or raises 401)

Any route that needs authentication just adds:
    current_user: User = Depends(get_current_user)
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


# ---------------------------------------------------------------------------
# OAuth2 scheme — tells FastAPI where to find the token
# ---------------------------------------------------------------------------
# OAuth2PasswordBearer does two things:
#   1. Looks for an "Authorization: Bearer <token>" header on incoming requests
#      and extracts just the <token> part for us
#   2. Adds a 🔒 "Authorize" button to the /docs Swagger UI so you can
#      paste in your token and test protected routes interactively
#
# tokenUrl="/auth/login" tells the Swagger UI which endpoint to use for
# getting a token. It doesn't affect your actual code — it's just for docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """
    FastAPI dependency that extracts and validates the JWT,
    then returns the corresponding User from the database.
    If anything fails (bad token, expired, user deleted), we raise 401.
    """

    # --- Step 1: Decode and verify the JWT ---
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- Step 2: Extract the user ID from the token ---
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
