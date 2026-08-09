"""
api/routes/auth.py — Registration & Login Endpoints

Two endpoints that handle the entire auth flow:

  POST /auth/register
    → "I'm new, create my account"
    → Hashes password, inserts user, returns user info (never the hash)

  POST /auth/login
    → "I already have an account, let me in"
    → Verifies password, creates a JWT, returns the token
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse
from app.api.dependencies import get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> UserResponse:

    # --- Step 1: Check if email already exists ---
    existing_user = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # --- Step 2: Hash the password ---
    hashed = hash_password(payload.password)

    # --- Step 3: Create the User object and save it ---
    new_user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hashed,
    )
    db.add(new_user)        # stage the insert (like git add)
    await db.commit()       # actually write to the database (like git commit)
    await db.refresh(new_user)  # reload from DB to get server-generated fields (like id, created_at that PostgreSQL fills in)

    # --- Step 4: Return user info (Pydantic strips out password_hash) ---
    return UserResponse.model_validate(new_user)

@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:

    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Return the currently authenticated user's info.

    This route exists to prove the JWT protection works.
    Depends(get_current_user) runs BEFORE this function body:
      1. Extracts the token from the Authorization header
      2. Verifies the JWT
      3. Looks up the user in the DB
      4. Passes the User object as current_user
    If any step fails, FastAPI returns 401 before we even get here.
    """
    return UserResponse.model_validate(current_user)
