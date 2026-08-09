from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once when the server starts, and once when it shuts down.
    
    "lifespan" is FastAPI's way of handling startup/shutdown logic.
    We use it here to:
      1. Verify the DB connection works on startup
      2. Cleanly close the connection pool on shutdown
    """
    # --- STARTUP ---
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(f"[OK] DB connected - SELECT 1 returned: {result.scalar()}")
    
    yield  # <-- app runs here, serving requests
    
    # --- SHUTDOWN ---
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
