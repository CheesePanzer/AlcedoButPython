import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alcedo import Configuration, DatabaseOptions, Entity
from example.domain import dormitory, student  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

configuration = Configuration.load(Path(__file__).parents[1])
database = configuration.bind(DatabaseOptions, "database")
database_url = database.url
sqlite_prefix = "sqlite+aiosqlite:///./"
if database_url.startswith(sqlite_prefix):
    relative_path = database_url[len(sqlite_prefix):]
    database_url = (
        f"sqlite+aiosqlite:///{(configuration.base_path / relative_path).as_posix()}"
    )
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Entity.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
