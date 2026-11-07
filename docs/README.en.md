# Alcedo User Guide

English | [简体中文](README.md)

Alcedo is a lightweight DDD foundation for FastAPI and SQLAlchemy Async. It
provides:

- Entity and aggregate-root base classes
- A repository base with row-locking queries
- Unit of Work and a transaction decorator
- Constructor injection with managed lifetimes
- FastAPI request-scope integration
- Unified RFC 7807-style error responses
- Concise HTTP response helpers

The recommended call flow is:

```text
FastAPI Controller
    -> Application Service
        -> Domain Entity / Domain Service
            -> Repository
                -> SQLAlchemy AsyncSession

Transaction boundary: Application Service + @transactional
```

## Installation

Install from the project root:

```bash
python -m pip install -e ".[dev]"
```

Alcedo requires Python 3.14 or later and uses SQLAlchemy's asynchronous API.

## Initialization

Place `appsettings.yaml` beside the application entry point and load
configuration from that directory:

```python
from fastapi import FastAPI
from alcedo import configure_alcedo

app = FastAPI()

runtime = configure_alcedo(app)
```

This call:

- Creates the SQLAlchemy `AsyncEngine`
- Creates the `async_sessionmaker`
- Registers a request-scoped `AsyncSession`
- Registers a request-scoped `UnitOfWork`
- Creates the DI `ServiceProvider`
- Integrates with the FastAPI lifespan
- Registers global exception handling
- Disposes the provider and engine when the application stops
- Enables foreign-key enforcement when using SQLite

Options:

| Option | Default | Description |
| --- | --- | --- |
| `database_url` | Required | SQLAlchemy asynchronous database URL |
| `metadata` | Framework `Entity.metadata` | Override when using a custom declarative base |
| `create_schema` | `False` | Calls `create_all` at startup; intended for demos and tests |
| `echo` | `False` | Enables SQLAlchemy SQL logging |
| `display_sensitive_errors` | `False` | Exposes details of unknown exceptions to clients |

Use Alembic for database migrations in production and leave `create_schema`
disabled.

When neither `database_url` nor `configuration` is supplied,
`configure_alcedo(app)` loads configuration by convention. Call it only once for
each application.

The function entry point remains available when a project must use the native
`FastAPI` class:

```python
from pathlib import Path

from fastapi import FastAPI
from alcedo import Configuration, configure_alcedo

app = FastAPI()
configuration = Configuration.load(Path(__file__).parent)
runtime = configure_alcedo(app, configuration=configuration)
```

## Configuration and Options

Alcedo provides startup-time configuration with immutable runtime values. Hot
reload is intentionally not supported.

YAML is recommended:

```yaml
# appsettings.yaml
database:
  url: postgresql+asyncpg://app:change-me@localhost:5432/app
  echo: false
  create_schema: false

presentation:
  display_sensitive_errors: false

mail:
  host: smtp.example.com
  port: 587
```

Convention-based initialization does not require an explicit
`Configuration.load()` call:

```python
from fastapi import FastAPI
from alcedo import configure_alcedo

app = FastAPI()
runtime = configure_alcedo(app)
```

The selected application directory may contain exactly one base file:

```text
appsettings.yaml
appsettings.yml
appsettings.json
```

An explicit file or directory is also supported:

```python
from alcedo import Configuration

configuration = Configuration.load("config/appsettings.yaml")
configuration = Configuration.load("config")
runtime = configure_alcedo(app, configuration=configuration)
```

The environment defaults to `APP_ENVIRONMENT`. With `Production`, sources are
loaded with this precedence:

```text
1. appsettings.yaml
2. appsettings.Production.yaml, when present
3. APP__... environment variables, highest priority
```

Later sources override earlier ones. Environment variables are always the final
source of truth in a conflict and cannot be overridden by files. Configuration
keys are case-insensitive.

### Environment Variables and Secrets

Use double underscores for nested keys:

```powershell
$env:APP_ENVIRONMENT = "Production"
$env:APP__DATABASE__URL = "postgresql+asyncpg://app:secret@db:5432/app"
$env:APP__PRESENTATION__DISPLAY_SENSITIVE_ERRORS = "false"
```

Linux/macOS:

```bash
export APP_ENVIRONMENT=Production
export APP__DATABASE__URL='postgresql+asyncpg://app:secret@db:5432/app'
```

Do not commit database passwords or other secrets to `appsettings.yaml`. Keep
only non-secret defaults in the repository and inject secrets with environment
variables or a deployment secret manager.

Change the default `APP` prefix with `env_prefix`:

```python
Configuration.load("appsettings.yaml", env_prefix="MYAPP")
```

### Typed Options

Define a Pydantic options model:

```python
from pydantic import Field
from alcedo import OptionsBase


class MailOptions(OptionsBase):
    host: str
    port: int = Field(gt=0, le=65535)
```

Register it with the options center:

```python
runtime.options.add(MailOptions, "mail")
```

Resolve it directly:

```python
mail = runtime.options.get(MailOptions).value
```

Or inject it through DI:

```python
from alcedo import Options


class MailService:
    def __init__(self, options: Options[MailOptions]) -> None:
        self._settings = options.value
```

`DatabaseOptions` and `PresentationOptions` are built-in and are loaded by
`configure_alcedo()` from their corresponding sections. Because hot reload is not
supported, `Options[T].value` remains unchanged for the application lifetime.

## PostgreSQL and Database Migrations

Use `asyncpg` for asynchronous PostgreSQL connections:

```yaml
database:
  url: postgresql+asyncpg://app:password@localhost:5432/app
  create_schema: false
```

The framework includes `asyncpg` and Alembic. Migration configuration belongs
to the application and currently lives at `example/alembic.ini`. Manage
production schemas with Alembic:

```bash
python -m alembic -c example/alembic.ini revision --autogenerate -m "add account table"
python -m alembic -c example/alembic.ini upgrade head
python -m alembic -c example/alembic.ini downgrade -1
python -m alembic -c example/alembic.ini check
```

Migrations read the same appsettings files and environment variables as the
application. To migrate PostgreSQL, set the URL and run the upgrade:

```powershell
$env:APP__DATABASE__URL = "postgresql+asyncpg://app:secret@localhost:5432/app"
python -m alembic -c example/alembic.ini upgrade head
```

Recommended SQLite-to-PostgreSQL process:

1. Create the PostgreSQL database and a least-privilege application account.
2. Set `APP__DATABASE__URL` without committing the password.
3. Ensure `create_schema` is `false`.
4. Run `python -m alembic -c example/alembic.ini upgrade head`.
5. Start the application and run integration tests.

Alembic manages schema, not existing SQLite data. Use a one-time ETL script or
a PostgreSQL import tool when existing records must be transferred.

## Entities and Aggregate Roots

Derive regular entities from `Entity`:

```python
from alcedo import Entity
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Address(Entity):
    __tablename__ = "addresses"

    city: Mapped[str] = mapped_column(String(100))
```

Derive aggregate roots from `AggregateRoot`:

```python
from alcedo import AggregateRoot
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Account(AggregateRoot):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(100))

    @classmethod
    def create(cls, name: str) -> "Account":
        name = name.strip()
        if not name:
            raise ValueError("name cannot be empty")
        return cls(name=name)

    def rename(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("name cannot be empty")
        self.name = name
```

`Entity` generates a time-ordered UUID primary key in the application with the
standard-library `uuid7()`, so the ID is available immediately after
construction. `AggregateRoot` additionally provides:

- `version`: SQLAlchemy optimistic-concurrency column
- `created_at`
- `updated_at`

Change domain state through aggregate methods. Application services should not
bypass aggregate behavior to assemble business state directly.

The current simplified model uses the same classes for the domain and the
SQLAlchemy ORM. Database foreign keys and `relationship` declarations therefore
appear on entity mappings. Applications that require complete Domain and
Infrastructure isolation can use SQLAlchemy imperative mappings instead.

## Repository

Declare required persistence operations as a domain `Protocol`:

```python
from typing import Protocol
from uuid import UUID


class AccountRepository(Protocol):
    async def get(self, account_id: UUID) -> Account | None: ...
    async def get_for_update(self, account_id: UUID) -> Account | None: ...
    def add(self, account: Account) -> None: ...
    async def remove(self, account: Account) -> None: ...
```

Implement it in Infrastructure by deriving from the generic repository:

```python
from alcedo import SqlAlchemyRepository


class SqlAlchemyAccountRepository(SqlAlchemyRepository[Account]):
    entity_type = Account
```

`SqlAlchemyRepository` provides:

```python
await repository.get(entity_id)
await repository.get_for_update(entity_id)
await repository.get_for_share(entity_id)
await repository.list(offset=0, limit=100)
await repository.count()
repository.add(entity)
await repository.remove(entity)
```

Locking queries:

- `get_for_update()` acquires an exclusive row lock
- `get_for_share()` acquires a shared row lock

Locks are meaningful only inside an active transaction. PostgreSQL and MySQL
support the corresponding row-lock semantics; SQLite has no equivalent
row-level shared lock.

Repositories must not call `commit()`. Unit of Work exclusively controls commits
and rollbacks.

## Unit of Work

An application service receives `UnitOfWork` through its constructor and exposes
it as the `uow` attribute used by the decorator:

```python
from alcedo import UnitOfWork, transactional


class AccountApplicationService:
    def __init__(
        self,
        repository: AccountRepository,
        uow: UnitOfWork,
    ) -> None:
        self.repository = repository
        self.uow = uow

    @transactional
    async def create(self, name: str):
        account = Account.create(name)
        self.repository.add(account)
        return account.id

    @transactional
    async def rename(self, account_id, name: str) -> None:
        account = await self.repository.get_for_update(account_id)
        if account is None:
            raise AccountNotFound(account_id)
        account.rename(name)
```

`@transactional` behaves as follows:

```text
Enter application method
-> Begin transaction
-> Execute business operation
-> Flush
-> Commit on successful return
-> Roll back on exception
```

Nested `@transactional` calls join the current UoW and do not start another
transaction.

The UoW can also be executed directly:

```python
async def action():
    ...

result = await uow.execute(action)
```

### Transaction Isolation

Select isolation for a use case:

```python
from alcedo import IsolationLevel, transactional


@transactional(isolation_level=IsolationLevel.SERIALIZABLE)
async def allocate(self) -> None:
    ...
```

Or configure the default on a UoW instance:

```python
from alcedo import IsolationLevel, SqlAlchemyUnitOfWork

uow = SqlAlchemyUnitOfWork(
    session,
    isolation_level=IsolationLevel.REPEATABLE_READ,
)
```

Available enum values:

```text
READ_UNCOMMITTED
READ_COMMITTED
REPEATABLE_READ
SERIALIZABLE
AUTOCOMMIT
```

Actual support depends on the database and driver. Raw strings are accepted for
database-specific modes.

A nested transaction cannot replace the outer transaction's isolation level. An
attempt to do so raises `RuntimeError`.

## Dependency Injection

`configure_alcedo()` automatically registers:

| Service | Lifetime |
| --- | --- |
| `AsyncEngine` | Singleton |
| `async_sessionmaker` | Singleton |
| `AsyncSession` | Scoped |
| `UnitOfWork` | Scoped |
| `SqlAlchemyUnitOfWork` | Scoped |
| `ServiceProvider` | Singleton |
| `ServiceScopeFactory` | Singleton |

Register application services:

```python
services = runtime.services

services.add_scoped(
    AccountRepository,
    SqlAlchemyAccountRepository,
)
services.add_scoped(AccountApplicationService)
```

Three lifetimes are supported:

```python
services.add_singleton(Service)
services.add_scoped(Service)
services.add_transient(Service)
```

Instances and factories can also be registered:

```python
services.add_singleton(Settings, instance=settings)
services.add_scoped(Client, factory=lambda scope: Client(...))
```

Concrete classes are recursively resolved from constructor type annotations.
Protocols and abstract types require an explicit implementation binding.

### Lifetime Rules

Alcedo enforces strict lifetime rules: a dependency must have a lifetime equal
to or longer than its consumer.

```text
Singleton -> Singleton                 Allowed
Scoped    -> Singleton / Scoped        Allowed
Transient -> Singleton / Scoped /
             Transient                 Allowed
```

The following relationships are rejected:

```text
Singleton -> Scoped
Singleton -> Transient
Scoped    -> Transient
```

Direct and indirect captures of shorter-lived services raise
`InvalidLifetimeError`.

### Creating a Scope from a Singleton

A singleton that initiates short-lived work outside an HTTP request should
inject `ServiceScopeFactory`:

```python
from alcedo import ServiceScopeFactory


class CleanupJob:
    def __init__(self, scope_factory: ServiceScopeFactory) -> None:
        self._scope_factory = scope_factory

    async def run(self) -> None:
        async with self._scope_factory.create_scope() as scope:
            service = await scope.resolve(AccountApplicationService)
            await service.cleanup()
```

Create a separate scope for every background-job iteration. Scoped objects must
not escape the `async with` block or be retained by a singleton.

## FastAPI Controller Injection

Use `Inject[T]` to inject a container service into a FastAPI endpoint. `Inject`
bridges Alcedo DI to FastAPI parameter resolution; no separate dependency
provider is required:

```python
from fastapi import APIRouter
from alcedo import Inject

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    service: Inject[AccountApplicationService],
):
    return await service.get(account_id)
```

Each HTTP request creates one DI `ServiceScope`. Application services,
repositories, and the UoW resolved during the same request share one
`AsyncSession`. The scope disposes the session and other resources when the
request ends.

The framework scope primarily targets HTTP requests. Background tasks should
explicitly create a scope through `ServiceScopeFactory`; do not retain a scoped
service injected into a controller.

## Unified Error Handling

`configure_alcedo()` installs global exception handlers. Application and domain code
only need to raise framework errors:

```python
from alcedo import ConflictError, NotFoundError

raise NotFoundError(
    "account was not found",
    code="AccountNotFound",
)

raise ConflictError(
    "account name already exists",
    client_action="Refresh",
)
```

Built-in mappings:

| Exception | HTTP status |
| --- | ---: |
| `BadRequestError` | 400 |
| `UnauthorizedError` | 401 |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `TooManyRequestsError` | 429 |
| FastAPI `RequestValidationError` | 422 |
| SQLAlchemy `StaleDataError` | 409 |
| SQLAlchemy `IntegrityError` | 409 |
| Unknown exception | 500 |

Error responses use `application/problem+json`:

```json
{
  "type": "https://httpstatuses.com/404",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "account was not found",
  "instance": "/api/accounts/123",
  "traceId": "...",
  "innerErrorCode": "AccountNotFound"
}
```

The trace ID uses the `traceparent` or `x-request-id` request header when
available and is otherwise generated. Every handled exception is logged through
the `alcedo.presentation` logger.

Unknown exception details are hidden from clients by default. Expose them only
during local development:

```python
runtime = configure_alcedo(
    app,
    database_url,
    display_sensitive_errors=True,
)
```

## HTTP Response Helpers

Controllers can use concise response helpers:

```python
from alcedo import Created, NoContent, NotFound, Ok

return Ok()
return Ok(data)
return Created(entity_id)
return NoContent()
return NotFound("account was not found")
```

For business failures, prefer raising `NotFoundError`, `ConflictError`, or
another mapped exception so the global handler produces Problem Details.
`NotFound()` is intended for the less common case where a controller directly
expresses an HTTP result.

## Custom Middleware

Applications can use native FastAPI middleware:

```python
from fastapi import Request


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.tenant_id = request.headers.get("x-tenant-id")
    return await call_next(request)
```

Starlette middleware classes can also be registered:

```python
app.add_middleware(TenantMiddleware)
```

Alcedo uses FastAPI/Starlette global exception handlers. Exceptions raised by
controllers, dependency resolution, and ordinary application middleware enter
the unified error handler.

The following failures cannot be converted into HTTP Problem Details:

- Application startup or shutdown failure
- Failure after the response has started
- A `BaseException` that is not an `Exception`, such as `KeyboardInterrupt`
- Process crash or forced termination

## Recommended Project Layout

```text
app/
├── api/
│   └── controllers/
├── application/
│   ├── models.py
│   └── services.py
├── domain/
│   ├── entities.py
│   ├── exceptions.py
│   └── repositories.py
├── infrastructure/
│   ├── repositories.py
│   └── services.py
└── main.py
```

Responsibilities:

- Controllers handle HTTP input/output and invoke application services
- Application services orchestrate use cases and define transaction boundaries
- Domain entities and services enforce business rules
- Domain declares repository protocols
- Infrastructure implements repositories and service registration
- Repositories do not commit transactions
- Domain and Application do not depend on FastAPI `Depends`

## Minimal Complete Configuration

```python
from fastapi import FastAPI
from alcedo import configure_alcedo, Inject

app = FastAPI()

runtime = configure_alcedo(app)

runtime.services.add_scoped(
    AccountRepository,
    SqlAlchemyAccountRepository,
)
runtime.services.add_scoped(AccountApplicationService)

app.include_router(account_router)
```
