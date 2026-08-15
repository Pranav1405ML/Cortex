"""
schemas/message.py — Pydantic models for Message endpoints

MessageCreate: what the client sends when adding a message to a conversation.
MessageResponse: what we send back — includes the server-generated id and
created_at timestamp.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# REQUEST schemas
# ---------------------------------------------------------------------------

class MessageCreate(BaseModel):
    """Body of POST /conversations/{id}/messages."""
    role: str          # "user" or "assistant"
    content: str


# ---------------------------------------------------------------------------
# RESPONSE schemas
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    """Returned for any message endpoint."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
