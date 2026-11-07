from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from fastapi import Depends, FastAPI, Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql.schema import MetaData

from alcedo.configuration import (
    Configuration,
    DatabaseOptions,
    OptionsCenter,
    PresentationOptions,
)
from alcedo.di import (
    ServiceCollection,
    ServiceProvider,
    ServiceScope,
    ServiceScopeFactory,
)
from alcedo.domain import Entity
from alcedo.infrastructure import SqlAlchemyUnitOfWork, UnitOfWork
from alcedo.presentation import add_exception_handlers

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AlcedoRuntime:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    services: ServiceCollection
    provider: ServiceProvider
    options: OptionsCenter

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def uow(self) -> AsyncIterator[SqlAlchemyUnitOfWork]:
        async with self.session_factory() as session:
            yield SqlAlchemyUnitOfWork(session)


@dataclass(frozen=True, slots=True)
class _BootstrapOptions:
    configuration: Configuration
    database_url: str
    echo: bool
    create_schema: bool
    display_sensitive_errors: bool
    has_database_section: bool
    has_presentation_section: bool


def configure_alcedo(
    app: FastAPI,
    database_url: str | None = None,
    *,
    configuration: Configuration | None = None,
    metadata: MetaData | None = None,
    create_schema: bool = False,
    echo: bool = False,
    display_sensitive_errors: bool = False,
) -> AlcedoRuntime:
    """Configure SQLAlchemy and framework lifecycle in one call."""

    bootstrap = _resolve_bootstrap_options(
        database_url=database_url,
        configuration=configuration,
        create_schema=create_schema,
        echo=echo,
        display_sensitive_errors=display_sensitive_errors,
    )
    engine, session_factory = _create_database(bootstrap)
    runtime = _create_runtime(engine, session_factory, bootstrap)

    add_exception_handlers(
        app,
        display_sensitive_errors=bootstrap.display_sensitive_errors,
    )
    _enable_sqlite_foreign_keys(engine)
    _configure_lifespan(
        app,
        runtime,
        metadata or Entity.metadata,
        bootstrap.create_schema,
    )
    app.state.alcedo = runtime
    return runtime


def _resolve_bootstrap_options(
    *,
    database_url: str | None,
    configuration: Configuration | None,
    create_schema: bool,
    echo: bool,
    display_sensitive_errors: bool,
) -> _BootstrapOptions:
    configuration = configuration or Configuration.load()
    has_database_section = bool(configuration.section("database"))
    has_presentation_section = bool(configuration.section("presentation"))
    database = (
        configuration.bind(DatabaseOptions, "database")
        if has_database_section
        else None
    )
    presentation = (
        configuration.bind(PresentationOptions, "presentation")
        if has_presentation_section
        else None
    )
    resolved_url = database_url or (database.url if database else None)
    if resolved_url is None:
        raise ValueError("database URL is required")
    return _BootstrapOptions(
        configuration=configuration,
        database_url=resolved_url,
        echo=database.echo if database else echo,
        create_schema=database.create_schema if database else create_schema,
        display_sensitive_errors=(
            presentation.display_sensitive_errors
            if presentation
            else display_sensitive_errors
        ),
        has_database_section=has_database_section,
        has_presentation_section=has_presentation_section,
    )


def _create_database(
    bootstrap: _BootstrapOptions,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    database_url = _resolve_database_url(
        bootstrap.database_url,
        bootstrap.configuration.base_path,
    )
    engine = create_async_engine(database_url, echo=bootstrap.echo)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


def _resolve_database_url(database_url: str, base_path: Path) -> str:
    prefix = "sqlite+aiosqlite:///./"
    if database_url.startswith(prefix):
        relative_path = database_url[len(prefix):]
        return f"sqlite+aiosqlite:///{(base_path / relative_path).as_posix()}"
    return database_url


def _create_runtime(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    bootstrap: _BootstrapOptions,
) -> AlcedoRuntime:
    services = ServiceCollection()
    options = OptionsCenter(bootstrap.configuration, services)
    services.add_singleton(Configuration, instance=bootstrap.configuration)
    services.add_singleton(OptionsCenter, instance=options)
    if bootstrap.has_database_section:
        options.add(DatabaseOptions, "database")
    if bootstrap.has_presentation_section:
        options.add(PresentationOptions, "presentation")
    services.add_singleton(AsyncEngine, instance=engine)
    services.add_singleton(async_sessionmaker[AsyncSession], instance=session_factory)
    services.add_scoped(AsyncSession, factory=lambda _: session_factory())
    services.add_scoped(UnitOfWork, SqlAlchemyUnitOfWork)
    services.add_scoped(SqlAlchemyUnitOfWork)
    provider = services.build_provider()
    services.add_singleton(ServiceProvider, instance=provider)
    services.add_singleton(
        ServiceScopeFactory,
        instance=ServiceScopeFactory(provider),
    )
    return AlcedoRuntime(engine, session_factory, services, provider, options)


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _configure_lifespan(
    app: FastAPI,
    runtime: AlcedoRuntime,
    metadata: MetaData,
    create_schema: bool,
) -> None:
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def alcedo_lifespan(application: FastAPI):
        if create_schema:
            async with runtime.engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
        try:
            async with previous_lifespan(application):
                yield
        finally:
            await runtime.provider.close()
            await runtime.engine.dispose()

    app.router.lifespan_context = alcedo_lifespan


def inject(service: type):
    async def resolve(scope: ServiceScope = Depends(alcedo_scope)):
        return await scope.resolve(service)

    return resolve


async def alcedo_scope(request: Request):
    runtime: AlcedoRuntime = request.app.state.alcedo
    async with runtime.provider.create_scope() as scope:
        yield scope


class Inject(Generic[T]):
    def __class_getitem__(cls, service: type[T]) -> Any:
        from typing import Annotated

        return Annotated[service, Depends(inject(service))]
