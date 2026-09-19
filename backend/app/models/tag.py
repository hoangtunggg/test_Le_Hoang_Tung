import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.todo import Todo
    from app.models.user import User


todo_tags = Table(
    "todo_tags",
    Base.metadata,
    Column(
        "todo_id",
        ForeignKey("todos.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="tags",
        lazy="select",
    )
    todos: Mapped[list["Todo"]] = relationship(  # noqa: F821
        "Todo",
        secondary=todo_tags,
        back_populates="tags",
        passive_deletes=True,
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


Index("ix_tags_user_id", Tag.user_id)
Index("uq_tags_user_name_ci", Tag.user_id, func.lower(Tag.name), unique=True)
Index("ix_todo_tags_tag_id", todo_tags.c.tag_id)
Index("ix_todo_tags_todo_id", todo_tags.c.todo_id)
