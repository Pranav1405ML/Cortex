from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class User(Base):
    __tablename__ = "users"

    # --- COLUMNS ---
    # Primary key: a UUID like "550e8400-e29b-41d4-a716-446655440000"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # String(255) = max 255 characters. unique=True = no two users can share an email.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Just a display name, no uniqueness constraint needed
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # server_default=func.now() means PostgreSQL itself fills in the timestamp
    # when a row is inserted — your Python code doesn't need to set it.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # --- RELATIONSHIPS ---
    # This doesn't create a column! It tells SQLAlchemy:
    # "A User has many Conversations. If I delete a User, delete their Conversations too."
    # back_populates="user" means Conversation also has a .user attribute pointing back.
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
