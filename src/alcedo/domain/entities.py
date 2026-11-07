from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from alcedo.domain.time import utc_now


class Entity(DeclarativeBase):
    """Base for ORM-backed domain entities."""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", uuid4())
        for name, value in kwargs.items():
            if not hasattr(type(self), name):
                raise TypeError(f"{name!r} is not a mapped attribute of {type(self).__name__}")
            setattr(self, name, value)


class AggregateRoot(Entity):
    """Aggregate root with timestamps and SQLAlchemy optimistic locking."""

    __abstract__ = True

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.version}
