---
name: add-config
description: Add a configuration object with its env source factory, dature loader, validation, container wiring and tests. Use when asked to add a setting, an environment variable or a new external service to goldy.
---

# Adding a config

Four files move together. Skipping any one produces a setting that reads as
configured and is not.

## 1. The config object

`setup/configs/<name>_config.py` — a frozen, slotted dataclass with a docstring
per field explaining what it decides, not what it is.

```python
@dataclass(slots=True, frozen=True)
class ThingConfig:
    host: str
    port: int
    timeout_seconds: int = 10
```

Required fields have no default. A default that silently works is how a
deployment ends up pointing at the wrong place — `RabbitMQConfig.user` and
`password` are required for exactly that reason.

Derived values are properties. Percent-encode anything user-supplied that goes
into a URI; `RabbitMQConfig.uri` shows why.

## 2. The env source factory

`setup/bootstrap/sources/<name>_env_source_factory.py`, mapping fields to
variable names.

Name variables so they cannot collide with the environment at large. A field
called `path` picks up the system `PATH`.

## 3. The loader

`setup/bootstrap/loaders/<name>_config_loader.py`, with `V.root(...)`
validators. Error messages name the environment variable, because the person
reading them is looking at a deployment, not at this code.

Pass `secret_field_names=(...)` for anything credential-shaped — a startup
failure is a log, and the log must not contain the password.

Reusable bounds live in `loaders/consts.py`.

## 4. Wiring

- `setups/configs_setup.py` — add the field to `SharedConfigs`, load it in
  `load_shared_configs()`, and include it in `as_context()`. If only one process
  needs it, load it separately like `load_telegram_config()` instead.
- `ioc/providers/configs_provider.py` — `provider.from_context(provides=...)`.

Configs are never loaded inside the container: a container that read the
environment could not be built for a test.

## 5. Tests

- `tests/unit/factories/env_data_factories.py` — a valid payload.
- `tests/unit/factories/source_stubs.py` — a stub source mirroring the real
  factory, so a typo in the production mapping fails the test.
- `tests/unit/setup/test_infrastructure_config_loaders.py` — the derived values,
  every validator, and that secrets are masked in the error output.

## 6. Before reporting

```sh
just lint && just mypy && uv run --active pytest tests/unit/setup -q
```
