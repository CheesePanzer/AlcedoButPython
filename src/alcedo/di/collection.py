import inspect
from typing import Any

from alcedo.di.models import Factory, ServiceDescriptor, ServiceKey, ServiceLifetime
from alcedo.di.provider import ServiceProvider


class ServiceCollection:
    def __init__(self) -> None:
        self._descriptors: dict[ServiceKey, ServiceDescriptor] = {}

    def add_singleton(
        self,
        service: ServiceKey,
        implementation: type[Any] | None = None,
        *,
        instance: Any = None,
        factory: Factory | None = None,
    ) -> "ServiceCollection":
        if instance is not None:
            factory = lambda _: instance
        return self._add(
            service, implementation, factory, ServiceLifetime.SINGLETON
        )

    def add_scoped(
        self,
        service: ServiceKey,
        implementation: type[Any] | None = None,
        *,
        factory: Factory | None = None,
    ) -> "ServiceCollection":
        return self._add(service, implementation, factory, ServiceLifetime.SCOPED)

    def add_transient(
        self,
        service: ServiceKey,
        implementation: type[Any] | None = None,
        *,
        factory: Factory | None = None,
    ) -> "ServiceCollection":
        return self._add(service, implementation, factory, ServiceLifetime.TRANSIENT)

    def _add(
        self,
        service: ServiceKey,
        implementation: type[Any] | None,
        factory: Factory | None,
        lifetime: ServiceLifetime,
    ) -> "ServiceCollection":
        if implementation is None and factory is None:
            if not inspect.isclass(service):
                raise TypeError(f"{service!r} requires an implementation or factory")
            implementation = service
        self._descriptors[service] = ServiceDescriptor(
            service, implementation, factory, lifetime
        )
        return self

    def build_provider(self) -> ServiceProvider:
        return ServiceProvider(self._descriptors)
