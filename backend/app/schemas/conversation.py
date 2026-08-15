"""
schemas/conversation.py — Pydantic models for Conversation endpoints

ConversationCreate: what the client sends when creating a conversation.
ConversationResponse: what we send back (never exposes internal fields
like password hashes — though conversations don't have those, the pattern
stays consistent with auth schemas).
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# REQUEST schemas
# ---------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    """Body of POST /conversations. Title is optional — defaults to 'New Chat'."""
    title: str = "New Chat"


# ---------------------------------------------------------------------------
# RESPONSE schemas
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    """Returned for any conversation endpoint."""
    id: uuid.UUID
    title: str
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
