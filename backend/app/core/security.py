from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing setup
# ---------------------------------------------------------------------------
# CryptContext is passlib's "I'll manage the hashing algorithm for you" object.
# schemes=["bcrypt"] → use bcrypt (the gold standard for password hashing).
# deprecated="auto" → if we ever add a second scheme, passlib will
#   automatically re-hash old passwords on next login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    Returns:
        A JWT string like "eyJhbGciOiJIUzI1NiIs..."

    The token contains:
        - Whatever you passed in `data` (e.g. the user's ID)
        - An "exp" (expiration) timestamp
        - It's all signed with our JWT_SECRET_KEY so nobody can tamper with it

    """
    to_encode = data.copy()  # don't mutate the original dict

    # Set the expiration time
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Takes a JWT string, verifies its signature and expiry,
    and returns the payload dict (e.g. {"sub": "user-uuid", "exp": ...}).
    Raises JWTError if the token is invalid, expired, or tampered with.

    """
    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    return decoded

"""
Return type mismatch — jwt.decode() from python-jose has a type signature
that returns str | dict (because in some edge cases it can return a string). 
But your function declares -> dict. 
Pyright sees this as "you say it returns dict, but jwt.decode might return str".
In practice, with a properly signed JWT, 
it always returns a dict — so this is a false alarm. 
But the type checker doesn't know that.
The code works perfectly fine. These are just the type checker being strict. You don't need to change anything unless you want to silence the warnings.
"""