"""
crud/conversation.py — Database operations for Conversations

Each function takes a db session and the minimum data it needs.
The key design decision: get_conversation() filters by BOTH conversation id
AND user_id. This means the ownership check is baked directly into the query —
if the conversation doesn't belong to you, it simply returns None, same as
if it doesn't exist at all.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


async def create_conversation(db: AsyncSession, user_id: uuid.UUID, title: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    """
    This is the ownership check. By filtering on both columns:
      - If the conversation doesn't exist → None
      - If it exists but belongs to someone else → None (same result!)
    The caller can't distinguish the two cases, which is exactly what we want.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    """Return all conversations belonging to user_id, newest first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    conversation = await get_conversation(db, conversation_id, user_id)
    if conversation is None:
        return None
    await db.delete(conversation)
    await db.commit()
    return conversation
