import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tag import todo_tags

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.user import User


class Todo(Base):
    """Todo model."""

    __tablename__ = "todos"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="todos",
        lazy="select",
    )
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        "Tag",
        secondary=todo_tags,
        back_populates="todos",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Todo {self.title}>"


Index(
    "ix_todos_user_created_id_desc",
    Todo.user_id,
    Todo.created_at.desc(),
    Todo.id.desc(),
)
Index(
    "ix_todos_user_completed_created_at",
    Todo.user_id,
    Todo.completed,
    Todo.created_at,
)
