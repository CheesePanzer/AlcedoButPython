from typing import Protocol

import pytest

from alcedo import (
    InvalidLifetimeError,
    ServiceCollection,
    ServiceProvider,
    ServiceScopeFactory,
)


class Clock(Protocol):
    def now(self) -> int: ...


class TestClock:
    def now(self) -> int:
        return 42


class ScopedDependency:
    pass


class ExampleService:
    def __init__(self, clock: Clock, dependency: ScopedDependency) -> None:
        self.clock = clock
        self.dependency = dependency


async def test_constructor_injection_and_scoped_lifetime() -> None:
    services = ServiceCollection()
    services.add_singleton(Clock, TestClock)
    services.add_scoped(ScopedDependency)
    services.add_transient(ExampleService)
    provider = services.build_provider()

    async with provider.create_scope() as first_scope:
        first = await first_scope.resolve(ExampleService)
        second = await first_scope.resolve(ExampleService)
        assert first is not second
        assert first.dependency is second.dependency
        assert first.clock is second.clock
        assert first.clock.now() == 42

    async with provider.create_scope() as second_scope:
        third = await second_scope.resolve(ExampleService)
        assert third.dependency is not first.dependency
        assert third.clock is first.clock

    await provider.close()


class TransientDependency:
    pass


class SingletonWithTransient:
    def __init__(self, dependency: TransientDependency) -> None:
        self.dependency = dependency


class TransientWithScoped:
    def __init__(self, dependency: ScopedDependency) -> None:
        self.dependency = dependency


class SingletonWithIndirectScoped:
    def __init__(self, dependency: TransientWithScoped) -> None:
        self.dependency = dependency


class ScopedWithTransient:
    def __init__(self, dependency: TransientDependency) -> None:
        self.dependency = dependency


@pytest.mark.parametrize(
    "singleton_type",
    [SingletonWithTransient, SingletonWithIndirectScoped],
)
async def test_singleton_cannot_capture_shorter_lifetime(singleton_type) -> None:
    services = ServiceCollection()
    services.add_transient(TransientDependency)
    services.add_scoped(ScopedDependency)
    services.add_transient(TransientWithScoped)
    services.add_singleton(singleton_type)
    provider = services.build_provider()

    async with provider.create_scope() as scope:
        with pytest.raises(InvalidLifetimeError, match="singleton.*cannot depend"):
            await scope.resolve(singleton_type)

    await provider.close()


async def test_scoped_cannot_capture_transient() -> None:
    services = ServiceCollection()
    services.add_transient(TransientDependency)
    services.add_scoped(ScopedWithTransient)
    provider = services.build_provider()

    async with provider.create_scope() as scope:
        with pytest.raises(InvalidLifetimeError, match="scoped.*cannot depend"):
            await scope.resolve(ScopedWithTransient)

    await provider.close()


class ScopedWorker:
    def __init__(self, dependency: ScopedDependency) -> None:
        self.dependency = dependency

    async def run(self) -> ScopedDependency:
        return self.dependency


class SingletonJob:
    def __init__(self, scope_factory: ServiceScopeFactory) -> None:
        self._scope_factory = scope_factory

    async def run(self) -> ScopedDependency:
        async with self._scope_factory.create_scope() as scope:
            worker = await scope.resolve(ScopedWorker)
            return await worker.run()


async def test_singleton_can_create_scopes_for_scoped_work() -> None:
    services = ServiceCollection()
    services.add_scoped(ScopedDependency)
    services.add_scoped(ScopedWorker)
    services.add_singleton(SingletonJob)
    provider = services.build_provider()
    services.add_singleton(ServiceProvider, instance=provider)
    services.add_singleton(
        ServiceScopeFactory,
        instance=ServiceScopeFactory(provider),
    )

    async with provider.create_scope() as scope:
        job = await scope.resolve(SingletonJob)

    first = await job.run()
    second = await job.run()
    assert first is not second

    await provider.close()
