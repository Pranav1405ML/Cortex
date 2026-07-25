from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

"""
from __future__ import annotations — makes all annotations strings by default, ensuring consistency with SQLAlchemy's forward-reference pattern.
from typing import TYPE_CHECKING — a special constant that is True only during static analysis.
if TYPE_CHECKING: block — imports Conversation only for the type checker, never at runtime, so there's no risk of circular imports.
"""
if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Which conversation this message belongs to
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # "user" or "assistant" — who sent this message
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Text (not String) = unlimited length. Good for message content
    # which could be very long.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # .conversation lets you do: message.conversation → gets the Conversation object
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
