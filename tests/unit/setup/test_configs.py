"""The connection strings each config derives from its parts.

These are the values that decide where the service actually connects, and a
wrong one fails far from here — usually as an authentication error nobody
traces back to a missing character in a URI.
"""

import dataclasses

import pytest

from tests.unit.factories.config_factories import (
    create_postgres_config,
    create_rabbitmq_config,
    create_redis_config,
)


def test_postgres_uri_uses_driver_credentials_and_database() -> None:
    config = create_postgres_config(
        user="app",
        password="s3cr3t",
        host="db.internal",
        port=6432,
        db_name="prod",
        driver="asyncpg",
    )

    assert config.uri == "postgresql+asyncpg://app:s3cr3t@db.internal:6432/prod"


def test_postgres_uri_reflects_the_configured_driver() -> None:
    config = create_postgres_config(driver="psycopg")

    assert config.uri.startswith("postgresql+psycopg://")


def test_redis_omits_credentials_when_no_password_is_set() -> None:
    """An empty password must not leave a stray ``@`` the server would reject."""
    config = create_redis_config()

    assert config.worker_uri == "redis://localhost:6379/1"


def test_redis_names_the_acl_user_when_one_is_set() -> None:
    """Without the username the server applies ``default``, which has every grant."""
    config = create_redis_config(user="app", password="s3cr3t")

    assert config.worker_uri == "redis://app:s3cr3t@localhost:6379/1"


def test_rabbitmq_uri_encodes_the_default_virtual_host() -> None:
    """A bare ``/`` would read as an empty name and connect somewhere else."""
    config = create_rabbitmq_config()

    assert config.uri == "amqp://guest:guest@localhost:5672/%2F"


def test_rabbitmq_uri_escapes_credentials_that_would_split_it() -> None:
    config = create_rabbitmq_config(user="a/b", password="p@ss/word")

    assert config.uri == "amqp://a%2Fb:p%40ss%2Fword@localhost:5672/%2F"


@pytest.mark.parametrize(
    "config",
    (
        create_postgres_config(),
        create_redis_config(),
        create_rabbitmq_config(),
    ),
)
def test_configs_are_immutable(config: object) -> None:
    """Configuration read at startup must not drift while the process runs."""
    field_name = "port"

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(config, field_name, 1)
