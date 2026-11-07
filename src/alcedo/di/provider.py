import inspect
from contextlib import AsyncExitStack
from typing import Any, get_type_hints

from alcedo.di.models import (
    LIFETIME_RANK,
    InvalidLifetimeError,
    ServiceDescriptor,
    ServiceKey,
    ServiceLifetime,
)


class ServiceProvider:
    def __init__(self, descriptors: dict[ServiceKey, ServiceDescriptor]) -> None:
        self._descriptors = descriptors
        self._singletons: dict[ServiceKey, Any] = {}
        self._exit_stack = AsyncExitStack()

    def create_scope(self) -> "ServiceScope":
        return ServiceScope(self)

    async def resolve(self, service: ServiceKey) -> Any:
        async with self.create_scope() as scope:
            return await scope.resolve(service)

    async def close(self) -> None:
        await self._exit_stack.aclose()


class ServiceScopeFactory:
    def __init__(self, provider: ServiceProvider) -> None:
        self._provider = provider

    def create_scope(self) -> "ServiceScope":
        return self._provider.create_scope()


class ServiceScope:
    def __init__(self, provider: ServiceProvider) -> None:
        self._provider = provider
        self._scoped: dict[ServiceKey, Any] = {}
        self._resolving: list[ServiceKey] = []
        self._resolving_descriptors: list[ServiceDescriptor] = []
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "ServiceScope":
        await self._exit_stack.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._exit_stack.__aexit__(*exc_info)

    async def resolve(self, service: ServiceKey) -> Any:
        descriptor = self._get_descriptor(service)
        self._validate_lifetime(descriptor)

        cache = self._cache_for(descriptor.lifetime)
        if cache is not None and service in cache:
            return cache[service]

        if service in self._resolving:
            chain = " -> ".join(
                _service_name(item) for item in [*self._resolving, service]
            )
            raise RuntimeError(f"circular dependency detected: {chain}")

        self._resolving.append(service)
        self._resolving_descriptors.append(descriptor)
        try:
            instance = await self._create(descriptor)
            if cache is not None:
                cache[service] = instance
            return instance
        finally:
            self._resolving_descriptors.pop()
            self._resolving.pop()

    def _get_descriptor(self, service: ServiceKey) -> ServiceDescriptor:
        descriptor = self._provider._descriptors.get(service)
        if descriptor is not None:
            return descriptor
        if inspect.isclass(service) and not _is_abstract(service):
            return ServiceDescriptor(
                service, service, None, ServiceLifetime.TRANSIENT
            )
        raise LookupError(f"service {service!r} is not registered")

    def _validate_lifetime(self, descriptor: ServiceDescriptor) -> None:
        longer_lived_owner = next(
            (
                item
                for item in self._resolving_descriptors
                if LIFETIME_RANK[item.lifetime]
                > LIFETIME_RANK[descriptor.lifetime]
            ),
            None,
        )
        if longer_lived_owner is not None:
            raise InvalidLifetimeError(
                f"{_service_name(longer_lived_owner.key)} "
                f"({longer_lived_owner.lifetime.value}) cannot depend on "
                f"{_service_name(descriptor.key)} ({descriptor.lifetime.value})"
            )

    def _cache_for(self, lifetime: ServiceLifetime) -> dict[ServiceKey, Any] | None:
        if lifetime == ServiceLifetime.SINGLETON:
            return self._provider._singletons
        if lifetime == ServiceLifetime.SCOPED:
            return self._scoped
        return None

    async def _create(self, descriptor: ServiceDescriptor) -> Any:
        if descriptor.factory is not None:
            value = descriptor.factory(self)
            instance = await value if inspect.isawaitable(value) else value
        else:
            instance = await self._construct(descriptor.implementation)
        return await self._track_resource(instance, descriptor.lifetime)

    async def _construct(self, implementation: type[Any] | None) -> Any:
        if implementation is None:
            raise TypeError("service descriptor has no implementation")
        signature = inspect.signature(implementation.__init__)
        hints = get_type_hints(implementation.__init__)
        kwargs: dict[str, Any] = {}
        for name, parameter in signature.parameters.items():
            if name == "self" or parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            dependency = hints.get(name)
            if dependency is None:
                if parameter.default is not inspect.Parameter.empty:
                    continue
                raise TypeError(
                    f"{implementation.__name__}.{name} requires a type annotation"
                )
            if parameter.default is not inspect.Parameter.empty and not self._can_resolve(
                dependency
            ):
                continue
            kwargs[name] = await self.resolve(dependency)
        return implementation(**kwargs)

    def _can_resolve(self, service: ServiceKey) -> bool:
        if service in self._provider._descriptors:
            return True
        return inspect.isclass(service) and not _is_abstract(service)

    async def _track_resource(
        self, instance: Any, lifetime: ServiceLifetime
    ) -> Any:
        stack = (
            self._provider._exit_stack
            if lifetime == ServiceLifetime.SINGLETON
            else self._exit_stack
        )
        if hasattr(instance, "__aenter__") and hasattr(instance, "__aexit__"):
            return await stack.enter_async_context(instance)
        if hasattr(instance, "aclose"):
            stack.push_async_callback(instance.aclose)
        elif hasattr(instance, "close"):
            stack.callback(instance.close)
        return instance


def _is_abstract(service: type[Any]) -> bool:
    return inspect.isabstract(service) or bool(getattr(service, "_is_protocol", False))


def _service_name(service: ServiceKey) -> str:
    return getattr(service, "__name__", repr(service))
