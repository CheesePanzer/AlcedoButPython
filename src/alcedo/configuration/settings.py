import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import TypeAdapter

T = TypeVar("T")


class Configuration:
    """Immutable-at-runtime configuration assembled from files and environment."""

    def __init__(
        self,
        values: dict[str, Any] | None = None,
        *,
        base_path: str | Path | None = None,
    ) -> None:
        self._values = deepcopy(values or {})
        self.base_path = Path(base_path or Path.cwd()).resolve()

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        *,
        environment: str | None = None,
        env_prefix: str = "APP",
    ) -> "Configuration":
        values: dict[str, Any] = {}
        file_path = _resolve_settings_path(path)
        environment = environment or os.getenv(f"{env_prefix}_ENVIRONMENT")
        if file_path is not None:
            _merge(values, _read_file(file_path))
            if environment:
                environment_path = file_path.with_name(
                    f"{file_path.stem}.{environment}{file_path.suffix}"
                )
                if environment_path.exists():
                    _merge(values, _read_file(environment_path))
        _merge(values, _environment_values(env_prefix))
        base_path = file_path.parent if file_path is not None else Path.cwd()
        return cls(values, base_path=base_path)

    def section(self, path: str) -> dict[str, Any]:
        current: Any = self._values
        for part in path.split(":"):
            if not isinstance(current, dict):
                return {}
            current = current.get(part.lower(), {})
        return deepcopy(current) if isinstance(current, dict) else {}

    def bind(self, options_type: type[T], section: str) -> T:
        return TypeAdapter(options_type).validate_python(self.section(section))


def _read_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as stream:
        if path.suffix.lower() in {".yaml", ".yml"}:
            value = yaml.safe_load(stream) or {}
        elif path.suffix.lower() == ".json":
            value = json.load(stream)
        else:
            raise ValueError(f"unsupported configuration format: {path.suffix}")
    if not isinstance(value, dict):
        raise ValueError("configuration root must be an object")
    return _normalize_keys(value)


def _resolve_settings_path(path: str | Path | None) -> Path | None:
    if path is not None:
        candidate = Path(path)
        if candidate.is_dir():
            return _find_default_settings(candidate)
        return candidate
    return _find_default_settings(Path.cwd())


def _find_default_settings(directory: Path) -> Path | None:
    candidates = [
        directory / "appsettings.yaml",
        directory / "appsettings.yml",
        directory / "appsettings.json",
    ]
    existing = [candidate for candidate in candidates if candidate.exists()]
    if len(existing) > 1:
        names = ", ".join(str(candidate) for candidate in existing)
        raise ValueError(f"multiple appsettings files found: {names}")
    return existing[0] if existing else None


def _environment_values(prefix: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    marker = f"{prefix}__" if prefix else ""
    for name, value in os.environ.items():
        if marker and not name.upper().startswith(marker.upper()):
            continue
        key = name[len(marker):] if marker else name
        if "__" not in key and marker:
            continue
        target = result
        parts = [part.lower() for part in key.split("__") if part]
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        if parts:
            target[parts[-1]] = value
    return result


def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _normalize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key).lower(): _normalize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_keys(item) for item in value]
    return value
