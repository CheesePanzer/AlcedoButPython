from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alcedo.domain import Entity

TEntity = TypeVar("TEntity", bound=Entity)


class SqlAlchemyRepository(Generic[TEntity]):
    """Small repository base. Transaction control deliberately stays in UoW."""

    entity_type: type[TEntity]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: UUID) -> TEntity | None:
        return await self.session.get(self.entity_type, entity_id)

    async def get_for_update(self, entity_id: UUID) -> TEntity | None:
        statement = (
            select(self.entity_type)
            .where(self.entity_type.id == entity_id)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def get_for_share(self, entity_id: UUID) -> TEntity | None:
        statement = (
            select(self.entity_type)
            .where(self.entity_type.id == entity_id)
            .with_for_update(read=True)
        )
        return await self.session.scalar(statement)

    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[TEntity]:
        statement = select(self.entity_type).offset(offset).limit(limit)
        return (await self.session.scalars(statement)).all()

    async def count(self) -> int:
        statement = select(func.count()).select_from(self.entity_type)
        return await self.session.scalar(statement) or 0

    def add(self, entity: TEntity) -> None:
        self.session.add(entity)

    async def remove(self, entity: TEntity) -> None:
        await self.session.delete(entity)
