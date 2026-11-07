from pathlib import Path

from alcedo import (
    Configuration,
    Options,
    OptionsBase,
    OptionsCenter,
    ServiceCollection,
)


class FeatureOptions(OptionsBase):
    enabled: bool
    retries: int


async def test_file_environment_override_and_typed_options(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = tmp_path / "appsettings.yaml"
    settings.write_text(
        "feature:\n  enabled: false\n  retries: 2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP__FEATURE__ENABLED", "true")
    monkeypatch.setenv("APP__FEATURE__RETRIES", "5")

    configuration = Configuration.load(settings)
    services = ServiceCollection()
    center = OptionsCenter(configuration, services)
    options = center.add(FeatureOptions, "feature")

    assert options.value.enabled is True
    assert options.value.retries == 5
    assert center.get(FeatureOptions) is options

    provider = services.build_provider()
    async with provider.create_scope() as scope:
        resolved = await scope.resolve(Options[FeatureOptions])
        assert resolved is options
    await provider.close()


def test_conventional_environment_file_and_environment_priority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "appsettings.yaml").write_text(
        "feature:\n  enabled: false\n  retries: 1\n",
        encoding="utf-8",
    )
    (tmp_path / "appsettings.Production.yaml").write_text(
        "feature:\n  retries: 2\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENVIRONMENT", "Production")
    monkeypatch.setenv("APP__FEATURE__RETRIES", "3")

    configuration = Configuration.load()
    options = configuration.bind(FeatureOptions, "feature")

    assert options.enabled is False
    assert options.retries == 3
