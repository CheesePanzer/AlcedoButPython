from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

ServiceKey = Any
Factory = Callable[["ServiceScope"], Any | Awaitable[Any]]


class ServiceLifetime(StrEnum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


LIFETIME_RANK = {
    ServiceLifetime.TRANSIENT: 1,
    ServiceLifetime.SCOPED: 2,
    ServiceLifetime.SINGLETON: 3,
}


class InvalidLifetimeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ServiceDescriptor:
    key: ServiceKey
    implementation: type[Any] | None
    factory: Factory | None
    lifetime: ServiceLifetime


# Only used for the factory type without importing provider at runtime.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alcedo.di.provider import ServiceScope
