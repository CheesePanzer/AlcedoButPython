from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

from alcedo.di import ServiceCollection

if TYPE_CHECKING:
    from alcedo.configuration.settings import Configuration

T = TypeVar("T")


class OptionsBase(BaseModel):
    """Base class for strongly typed application options."""


class Options(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


class OptionsCenter:
    def __init__(
        self,
        configuration: "Configuration",
        services: ServiceCollection,
    ) -> None:
        self.configuration = configuration
        self._services = services
        self._values: dict[type[Any], Any] = {}

    def add(self, options_type: type[T], section: str) -> Options[T]:
        value = self.configuration.bind(options_type, section)
        wrapper = Options(value)
        self._values[options_type] = wrapper
        self._services.add_singleton(Options[options_type], instance=wrapper)
        return wrapper

    def get(self, options_type: type[T]) -> Options[T]:
        try:
            return self._values[options_type]
        except KeyError as exception:
            raise LookupError(
                f"options {options_type.__name__} are not registered"
            ) from exception


class DatabaseOptions(OptionsBase):
    url: str
    echo: bool = False
    create_schema: bool = False


class PresentationOptions(OptionsBase):
    display_sensitive_errors: bool = False
