from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from enum import StrEnum
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, cast, overload

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")
P = ParamSpec("P")


class IsolationLevel(StrEnum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"
    AUTOCOMMIT = "AUTOCOMMIT"


IsolationLevelOption = IsolationLevel | str


class UnitOfWork(Protocol):
    async def execute(
        self,
        action: Callable[[], Awaitable[T]],
        *,
        isolation_level: IsolationLevelOption | None = None,
    ) -> T: ...


class SqlAlchemyUnitOfWork:
    """Runs a use case in one transaction and joins nested executions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        isolation_level: IsolationLevelOption | None = None,
    ) -> None:
        self._session = session
        self._default_isolation_level = _isolation_value(isolation_level)
        self._depth: ContextVar[int] = ContextVar("alcedo_uow_depth", default=0)
        self._isolation_level: ContextVar[str | None] = ContextVar(
            "alcedo_uow_isolation_level", default=None
        )

    async def execute(
        self,
        action: Callable[[], Awaitable[T]],
        *,
        isolation_level: IsolationLevelOption | None = None,
    ) -> T:
        depth = self._depth.get()
        explicit_level = _isolation_value(isolation_level)
        requested_level = explicit_level or self._default_isolation_level
        if depth > 0:
            active_level = self._isolation_level.get()
            if explicit_level is not None and explicit_level != active_level:
                raise RuntimeError(
                    "cannot change isolation level inside an active unit of work"
                )
            return await action()

        depth_token = self._depth.set(depth + 1)
        isolation_token = self._isolation_level.set(requested_level)
        try:
            if requested_level is None:
                async with self._session.begin():
                    result = await action()
                    await self._session.flush()
                    return result

            await self._session.connection(
                execution_options={"isolation_level": requested_level}
            )
            try:
                result = await action()
                await self._session.flush()
                await self._session.commit()
                return result
            except BaseException:
                await self._session.rollback()
                raise
        finally:
            self._isolation_level.reset(isolation_token)
            self._depth.reset(depth_token)


@overload
def transactional(
    method: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]: ...


@overload
def transactional(
    method: None = None,
    *,
    isolation_level: IsolationLevelOption | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]: ...


def transactional(
    method: Callable[P, Awaitable[T]] | None = None,
    *,
    isolation_level: IsolationLevelOption | None = None,
) -> (
    Callable[P, Awaitable[T]]
    | Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]
):
    """Wrap an application method in its UoW, optionally selecting isolation."""

    def decorate(
        inner: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @wraps(inner)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not args:
                raise TypeError("@transactional must decorate an instance method")

            owner = cast(Any, args[0])
            uow: UnitOfWork | None = getattr(owner, "uow", None)
            if uow is None:
                raise RuntimeError(
                    f"{type(owner).__name__} must expose a 'uow' attribute"
                )

            async def action() -> T:
                return await inner(*args, **kwargs)

            return await uow.execute(action, isolation_level=isolation_level)

        return wrapper

    if method is None:
        return decorate
    return decorate(method)


def _isolation_value(level: IsolationLevelOption | None) -> str | None:
    return level.value if isinstance(level, IsolationLevel) else level
