# Alcedo 使用手册

[English](README.en.md) | 简体中文

Alcedo 是基于 FastAPI 和 SQLAlchemy Async 的轻量 DDD 基础框架，主要提供：

- 实体和聚合根基类
- Repository 基类和行锁查询
- Unit of Work 和事务装饰器
- 构造函数依赖注入及生命周期管理
- FastAPI 请求 Scope 集成
- RFC 7807 风格统一异常响应
- 简洁的 HTTP 响应辅助函数

推荐调用关系：

```text
FastAPI Controller
    -> Application Service
        -> Domain Entity / Domain Service
            -> Repository
                -> SQLAlchemy AsyncSession

事务边界：Application Service + @transactional
```

## 安装

在项目根目录安装：

```bash
python -m pip install -e ".[dev]"
```

Alcedo 要求 Python 3.14 或更高版本，并使用 SQLAlchemy 异步接口。

## 初始化

将 `appsettings.yaml` 放在应用入口文件所在目录，并从该目录加载配置：

```python
from fastapi import FastAPI
from alcedo import configure_alcedo

app = FastAPI()

runtime = configure_alcedo(app)
```

该调用会完成：

- 创建 SQLAlchemy `AsyncEngine`
- 创建 `async_sessionmaker`
- 注册请求级 `AsyncSession`
- 注册请求级 `UnitOfWork`
- 创建 DI `ServiceProvider`
- 接入 FastAPI lifespan
- 注册全局异常处理
- 应用关闭时释放 Provider 和 Engine
- SQLite 环境下启用外键约束

参数说明：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `database_url` | 必填 | SQLAlchemy 异步数据库 URL |
| `metadata` | 框架 `Entity.metadata` | 自定义 Declarative Base 时覆盖 Metadata |
| `create_schema` | `False` | 启动时调用 `create_all`，仅建议用于演示和测试 |
| `echo` | `False` | 输出 SQLAlchemy SQL 日志 |
| `display_sensitive_errors` | `False` | 是否向客户端显示未知异常详情 |

生产环境应使用 Alembic 管理数据库迁移，不应启用 `create_schema`。

未显式提供 `database_url` 或 `configuration` 时，`configure_alcedo(app)` 按约定
自动加载配置。该方法在同一个应用上只应调用一次。

如果项目必须使用原生 `FastAPI` 类，函数式入口仍然可用：

```python
from pathlib import Path

from fastapi import FastAPI
from alcedo import Configuration, configure_alcedo

app = FastAPI()
configuration = Configuration.load(Path(__file__).parent)
runtime = configure_alcedo(app, configuration=configuration)
```

## 配置与 Options

Alcedo 提供启动时加载、运行期只读的配置中心。不提供热重载。

推荐使用 YAML：

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

按约定初始化时不需要显式调用 `Configuration.load()`：

```python
from fastapi import FastAPI
from alcedo import configure_alcedo

app = FastAPI()
runtime = configure_alcedo(app)
```

指定的应用目录中只允许存在一个基础配置文件：

```text
appsettings.yaml
appsettings.yml
appsettings.json
```

也可以显式指定文件或目录：

```python
from alcedo import Configuration

configuration = Configuration.load("config/appsettings.yaml")
configuration = Configuration.load("config")
runtime = configure_alcedo(app, configuration=configuration)
```

环境名默认读取 `APP_ENVIRONMENT`。若值为 `Production`，加载顺序和优先级为：

```text
1. appsettings.yaml
2. appsettings.Production.yaml（存在时）
3. APP__... 环境变量（最高优先级）
```

后加载的来源覆盖先加载的来源。环境变量始终是冲突时的最终值，配置文件
无法覆盖环境变量。配置键不区分大小写。

### 环境变量与密钥

使用双下划线表达配置层级：

```powershell
$env:APP_ENVIRONMENT = "Production"
$env:APP__DATABASE__URL = "postgresql+asyncpg://app:secret@db:5432/app"
$env:APP__PRESENTATION__DISPLAY_SENSITIVE_ERRORS = "false"
```

Linux/macOS：

```bash
export APP_ENVIRONMENT=Production
export APP__DATABASE__URL='postgresql+asyncpg://app:secret@db:5432/app'
```

数据库密码等密钥不应提交到 `appsettings.yaml`。仓库中仅保留无密钥的默认配置，部署环境通过环境变量或 Secret Manager 注入。

可通过 `env_prefix` 修改默认的 `APP` 前缀：

```python
Configuration.load("appsettings.yaml", env_prefix="MYAPP")
```

### 类型化 Options

定义 Pydantic Options：

```python
from pydantic import Field
from alcedo import OptionsBase


class MailOptions(OptionsBase):
    host: str
    port: int = Field(gt=0, le=65535)
```

注册到 Options 中心：

```python
runtime.options.add(MailOptions, "mail")
```

直接获取：

```python
mail = runtime.options.get(MailOptions).value
```

通过 DI 注入：

```python
from alcedo import Options


class MailService:
    def __init__(self, options: Options[MailOptions]) -> None:
        self._settings = options.value
```

`DatabaseOptions` 和 `PresentationOptions` 是框架内置 Options，并由 `configure_alcedo()` 从相应配置节读取。由于不支持热重载，`Options[T].value` 在应用运行期间保持不变。

## PostgreSQL 与数据库迁移

PostgreSQL 异步连接使用 `asyncpg`：

```yaml
database:
  url: postgresql+asyncpg://app:password@localhost:5432/app
  create_schema: false
```

框架已包含 `asyncpg` 和 Alembic。迁移配置属于具体应用，当前位于
`example/alembic.ini`。生产数据库结构通过 Alembic 管理：

```bash
# 根据当前 Entity.metadata 生成迁移
python -m alembic -c example/alembic.ini revision --autogenerate -m "add account table"

# 应用全部迁移
python -m alembic -c example/alembic.ini upgrade head

# 回退一个版本
python -m alembic -c example/alembic.ini downgrade -1

# 检查模型是否存在未生成的变更
python -m alembic -c example/alembic.ini check
```

迁移进程读取与应用相同的 `appsettings` 和环境变量。因此迁移 PostgreSQL 时只需设置：

```powershell
$env:APP__DATABASE__URL = "postgresql+asyncpg://app:secret@localhost:5432/app"
python -m alembic -c example/alembic.ini upgrade head
```

将 SQLite 切换到 PostgreSQL 的推荐步骤：

1. 创建 PostgreSQL 数据库和最小权限应用账号。
2. 设置 `APP__DATABASE__URL`，不要将密码写入仓库。
3. 确认 `create_schema` 为 `false`。
4. 执行 `python -m alembic -c example/alembic.ini upgrade head` 创建结构。
5. 启动应用并执行集成测试。

Alembic 管理的是数据库结构，不负责搬运现有 SQLite 数据。需要迁移已有数据时，应另外编写一次性 ETL 脚本或使用 PostgreSQL 导入工具。

## 实体与聚合根

普通实体继承 `Entity`：

```python
from alcedo import Entity
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Address(Entity):
    __tablename__ = "addresses"

    city: Mapped[str] = mapped_column(String(100))
```

聚合根继承 `AggregateRoot`：

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

`Entity` 在应用侧使用标准库 `uuid7()` 生成具有时间顺序特征的 UUID 主键，
实体构造完成时即可获得 ID。`AggregateRoot` 额外提供：

- `version`：SQLAlchemy 乐观并发版本列
- `created_at`
- `updated_at`

领域状态应通过聚合方法修改，Application Service 不应绕过聚合行为直接拼装业务状态。

当前实现采用领域实体与 SQLAlchemy ORM 实体合一的简化模式。数据库外键和 `relationship` 因此定义在实体映射上；若需要完全隔离 Domain 和 Infrastructure，可改用 SQLAlchemy imperative mapping。

## Repository

领域层使用 `Protocol` 声明所需能力：

```python
from typing import Protocol
from uuid import UUID


class AccountRepository(Protocol):
    async def get(self, account_id: UUID) -> Account | None: ...
    async def get_for_update(self, account_id: UUID) -> Account | None: ...
    def add(self, account: Account) -> None: ...
    async def remove(self, account: Account) -> None: ...
```

Infrastructure 层继承通用实现：

```python
from alcedo import SqlAlchemyRepository


class SqlAlchemyAccountRepository(SqlAlchemyRepository[Account]):
    entity_type = Account
```

`SqlAlchemyRepository` 提供：

```python
await repository.get(entity_id)
await repository.get_for_update(entity_id)
await repository.get_for_share(entity_id)
await repository.list(offset=0, limit=100)
await repository.count()
repository.add(entity)
await repository.remove(entity)
```

锁查询映射：

- `get_for_update()` 使用排他行锁
- `get_for_share()` 使用共享行锁

锁必须在有效事务内使用。PostgreSQL 和 MySQL 支持相应行锁语义，SQLite 不提供等价的行级共享锁。

Repository 不得调用 `commit()`。事务提交和回滚统一由 Unit of Work 控制。

## 状态机

领域层提供轻量状态流和行为守卫。状态、Trigger 和 Action 推荐使用
`StrEnum`：

```python
from enum import StrEnum

from alcedo import StateActionGuard, StateFlow, StateTransition


class JobState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobTrigger(StrEnum):
    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"


flow = StateFlow(
    (
        StateTransition(JobState.CREATED, JobTrigger.START, JobState.RUNNING),
        StateTransition(JobState.RUNNING, JobTrigger.COMPLETE, JobState.COMPLETED),
        StateTransition(JobState.RUNNING, JobTrigger.FAIL, JobState.FAILED),
    )
)
```

在聚合方法中执行迁移：

```python
def complete(self) -> None:
    self.state = flow.transition(self.state, JobTrigger.COMPLETE)
```

可用操作：

```python
flow.can_transition(state, trigger)
flow.get_next_state(state, trigger)
flow.transition(state, trigger)
flow.allowed_triggers(state)
```

非法迁移会抛出 `InvalidStateTransitionError`。相同状态和 Trigger 的重复规则
会在创建 `StateFlow` 时直接报错。

Action 用于限制不改变状态的领域行为：

```python
guard = StateActionGuard(
    {
        JobAction.CANCEL: {JobState.CREATED, JobState.RUNNING},
        JobAction.RATE: {JobState.COMPLETED},
    }
)

guard.ensure_allowed(self.state, JobAction.RATE)
```

行为不允许时会抛出 `StateActionNotAllowedError`。状态机只负责领域规则，不负责
任务调度、持久化或工作流恢复。

## DTO 与 Command

Application 层的输入和输出应使用显式类型：

- `CommandBase` 标记应用用例输入
- `DtoBase` 标记跨 Application 边界返回的数据

```python
from alcedo import CommandBase, DtoBase
from pydantic import Field


class AccountCreateCommand(CommandBase):
    name: str = Field(max_length=100)


class AccountDto(DtoBase):
    id: UUID
    name: str
    version: int
```

`CommandBase` 默认拒绝未声明字段，避免调用方传入的数据被静默忽略。
`DtoBase` 默认启用 `from_attributes`，可以从领域实体或 ORM 实体转换：

```python
dto = AccountDto.model_validate(account)
```

Command 不应作为返回模型，DTO 也不应承担修改用例的输入职责。

## Unit of Work

Application Service 通过构造函数接收 `UnitOfWork`，并公开为 `uow` 属性：

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

`@transactional` 的行为：

```text
进入 Application 方法
-> 开启事务
-> 执行业务
-> flush
-> 正常返回时 commit
-> 抛出异常时 rollback
```

嵌套的 `@transactional` 调用会加入当前 UoW，不会重复开启事务。

也可以直接执行工作单元：

```python
async def action():
    ...

result = await uow.execute(action)
```

### 事务隔离级别

在单个用例上指定：

```python
from alcedo import IsolationLevel, transactional


@transactional(isolation_level=IsolationLevel.SERIALIZABLE)
async def allocate(self) -> None:
    ...
```

创建 UoW 时指定默认值：

```python
from alcedo import IsolationLevel, SqlAlchemyUnitOfWork

uow = SqlAlchemyUnitOfWork(
    session,
    isolation_level=IsolationLevel.REPEATABLE_READ,
)
```

可用枚举：

```text
READ_UNCOMMITTED
READ_COMMITTED
REPEATABLE_READ
SERIALIZABLE
AUTOCOMMIT
```

具体支持范围由数据库和驱动决定。也可以传入数据库特定的原始字符串。

嵌套事务不能修改外层事务的隔离级别，否则会抛出 `RuntimeError`。

## 依赖注入

`configure_alcedo()` 自动注册：

| 服务 | 生命周期 |
| --- | --- |
| `AsyncEngine` | Singleton |
| `async_sessionmaker` | Singleton |
| `AsyncSession` | Scoped |
| `UnitOfWork` | Scoped |
| `SqlAlchemyUnitOfWork` | Scoped |
| `ServiceProvider` | Singleton |
| `ServiceScopeFactory` | Singleton |

注册业务服务：

```python
services = runtime.services

services.add_scoped(
    AccountRepository,
    SqlAlchemyAccountRepository,
)
services.add_scoped(AccountApplicationService)
```

支持三种生命周期：

```python
services.add_singleton(Service)
services.add_scoped(Service)
services.add_transient(Service)
```

也可注册实例或工厂：

```python
services.add_singleton(Settings, instance=settings)
services.add_scoped(Client, factory=lambda scope: Client(...))
```

具体类会按照构造函数类型标注自动递归解析。`Protocol` 和抽象类型必须显式绑定实现。

### 生命周期规则

框架采用严格生命周期规则：依赖的生命周期必须大于或等于持有者。

```text
Singleton -> Singleton                 允许
Scoped    -> Singleton / Scoped        允许
Transient -> Singleton / Scoped /
             Transient                 允许
```

以下关系禁止：

```text
Singleton -> Scoped
Singleton -> Transient
Scoped    -> Transient
```

直接或间接捕获短生命周期服务都会抛出 `InvalidLifetimeError`。

### Singleton 显式创建 Scope

Singleton 若需要执行请求外的短周期任务，应注入 `ServiceScopeFactory`：

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

每轮后台任务应创建独立 Scope。Scoped 对象不能从 `async with` 块中返回或被 Singleton 保存。

## FastAPI Controller 注入

使用 `Inject[T]` 将容器服务注入 FastAPI Endpoint。`Inject` 是 Alcedo DI
与 FastAPI 参数解析之间的桥接标记，不需要另外定义 dependency provider：

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

每次 HTTP 请求创建一个 DI `ServiceScope`。同一请求内的 Application Service、Repository 和 UoW 共享同一个 `AsyncSession`。请求结束后，Scope 自动释放 Session 等资源。

框架 Scope 主要面向 HTTP 请求。后台任务应通过 `ServiceScopeFactory` 显式创建 Scope，不应保存 Controller 中注入的 Scoped 服务。

## 统一错误处理

`configure_alcedo()` 会自动注册全局异常处理器。Application 或 Domain 只需抛出框架异常：

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

内置映射：

| 异常 | HTTP 状态码 |
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
| 未知异常 | 500 |

错误响应使用 `application/problem+json`：

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

`traceId` 优先使用请求头中的 `traceparent` 或 `x-request-id`，否则自动生成。所有处理过的异常通过 `alcedo.presentation` logger 记录。

未知异常详情默认不会返回客户端。仅在本地开发时开启：

```python
runtime = configure_alcedo(
    app,
    database_url,
    display_sensitive_errors=True,
)
```

## HTTP 响应辅助函数

Controller 可以使用简洁的响应辅助函数：

```python
from alcedo import Created, NoContent, NotFound, Ok

return Ok()
return Ok(data)
return Created(entity_id)
return NoContent()
return NotFound("account was not found")
```

对于业务失败，优先抛出 `NotFoundError`、`ConflictError` 等异常，由统一异常处理生成 Problem Details。`NotFound()` 更适用于 Controller 需要直接表达 HTTP 结果的特殊情况。

## 自定义 Middleware

项目可以使用 FastAPI 原生中间件：

```python
from fastapi import Request


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.tenant_id = request.headers.get("x-tenant-id")
    return await call_next(request)
```

也可以注册 Starlette Middleware 类：

```python
app.add_middleware(TenantMiddleware)
```

Alcedo 使用 FastAPI/Starlette 全局 Exception Handler，Controller、依赖解析和普通项目 Middleware 抛出的 `Exception` 都会进入统一错误处理。

以下错误不能转换为 HTTP Problem Details：

- 应用 startup 或 shutdown 失败
- 响应已经开始发送后发生的异常
- `KeyboardInterrupt` 等非 `Exception` 的 `BaseException`
- 进程崩溃或强制退出

## 推荐项目结构

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

职责约束：

- Controller 只处理 HTTP 输入输出并调用 Application Service
- Application Service 编排用例并定义事务边界
- Domain 实体和服务维护业务规则
- Domain 声明 Repository Protocol
- Infrastructure 实现 Repository 和服务注册
- Repository 不提交事务
- Domain 和 Application 不依赖 FastAPI `Depends`

## 最小完整配置

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
