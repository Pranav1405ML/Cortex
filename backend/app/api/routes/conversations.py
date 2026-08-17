"""
api/routes/conversations.py — Conversation & Message Endpoints

All routes require authentication (get_current_user dependency).

Ownership enforcement:
  Every route that touches a specific conversation calls
  crud.conversation.get_conversation(db, id, current_user.id).
  That query filters by BOTH conversation id AND user_id, so:
    - Conversation doesn't exist → 404
    - Conversation exists but belongs to someone else → 404 (same error!)
  This prevents information leakage: an attacker can't tell whether
  a conversation id is valid or not.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.crud import conversation as crud_conversation
from app.crud import message as crud_message
from app.db.session import get_db
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services.ai_service import AIServiceError, generate_reply


router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ---------------------------------------------------------------------------
# Helper — avoids repeating the same ownership-check + 404 in every route
# ---------------------------------------------------------------------------
async def _get_owned_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID,):
    """
    Fetch a conversation that belongs to user_id, or raise 404.
    Used by GET /conversations/{id}, DELETE, and the message routes.
    """
    conversation = await crud_conversation.get_conversation(db, conversation_id, user_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


# ---------------------------------------------------------------------------
# Conversation CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ConversationResponse:
    conversation = await crud_conversation.create_conversation(db, user_id=current_user.id, title=payload.title)
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[ConversationResponse]:
    """List all conversations belonging to the current user."""
    conversations = await crud_conversation.list_conversations(db, current_user.id)
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ConversationResponse:
    """
    Get a single conversation by id.
    Returns 404 if it doesn't exist OR if it belongs to someone else.
    """
    conversation = await _get_owned_conversation(db, conversation_id, current_user.id)
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    """
    Delete a conversation. Returns 404 if not found or not owned.
    204 No Content on success (nothing to return).
    """
    deleted = await crud_conversation.delete_conversation(db, conversation_id, current_user.id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )


# ---------------------------------------------------------------------------
# Message endpoints (nested under a conversation)
# ---------------------------------------------------------------------------

@router.post("/{conversation_id}/messages", response_model=list[MessageResponse], status_code=status.HTTP_201_CREATED,)
async def create_message(conversation_id: uuid.UUID, payload: MessageCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[MessageResponse]:
    """
    Send a user message and get an AI reply.

    Flow:
      1. Verify the conversation belongs to the current user.
      2. Store the incoming user message in the database.
      3. Fetch the full conversation history (including the new message).
      4. Send the history to Gemini and get an assistant reply.
      5. Store the assistant reply in the database.
      6. Return both the user message and the assistant reply.

    On AI failure, returns 502 Bad Gateway with a clean error message
    (the user's message is still persisted).
    """
    # 1. Ownership check — 404 if not found or not theirs
    await _get_owned_conversation(db, conversation_id, current_user.id)

    # 2. Store the user's message
    user_message = await crud_message.create_message(
        db, conversation_id=conversation_id, role=payload.role, content=payload.content,
    )

    # 3. Fetch full conversation history (chronological)
    all_messages = await crud_message.list_messages(db, conversation_id)
    history = [{"role": m.role, "content": m.content} for m in all_messages]

    # 4. Call the AI service
    try:
        reply_text = await generate_reply(history)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc

    # 5. Store the assistant's reply
    assistant_message = await crud_message.create_message(
        db, conversation_id=conversation_id, role="assistant", content=reply_text,
    )

    # 6. Return both messages
    return [
        MessageResponse.model_validate(user_message),
        MessageResponse.model_validate(assistant_message),
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[MessageResponse]:
    """
    List all messages in a conversation (chronological order).
    Verifies the conversation belongs to the current user first.
    """
    # Ownership check — 404 if not found or not theirs
    await _get_owned_conversation(db, conversation_id, current_user.id)

    messages = await crud_message.list_messages(db, conversation_id)
    return [MessageResponse.model_validate(m) for m in messages]
