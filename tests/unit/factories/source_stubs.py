"""One stub source per config, serving valid values keyed by env var name."""

from goldy.setup.bootstrap.sources.admin_env_source_factory import (
    AdminEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.alchemy_env_source_factory import (
    SQLAlchemyEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.catalog_env_source_factory import (
    CatalogEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.postgres_env_source_factory import (
    PostgresEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.rabbitmq_env_source_factory import (
    RabbitMQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.redis_env_source_factory import (
    RedisEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.taskiq_env_source_factory import (
    TaskIQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.telegram_env_source_factory import (
    TelegramEnvSourceFactory,
)
from tests.unit.factories.env_data_factories import (
    admin_env,
    catalog_env,
    postgres_env,
    rabbitmq_env,
    redis_env,
    sqlalchemy_env,
    taskiq_env,
    telegram_env,
)
from tests.unit.factories.stub_source_factory import StubSourceFactory


def postgres_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``POSTGRES_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        PostgresEnvSourceFactory(),
        postgres_env(**overrides),
    )


def sqlalchemy_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``DB_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        SQLAlchemyEnvSourceFactory(),
        sqlalchemy_env(**overrides),
    )


def redis_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``REDIS_*`` values; override any key."""
    return StubSourceFactory.mirroring(RedisEnvSourceFactory(), redis_env(**overrides))


def rabbitmq_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``RABBITMQ_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        RabbitMQEnvSourceFactory(),
        rabbitmq_env(**overrides),
    )


def taskiq_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``TASKIQ_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        TaskIQEnvSourceFactory(),
        taskiq_env(**overrides),
    )


def telegram_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``TELEGRAM_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        TelegramEnvSourceFactory(),
        telegram_env(**overrides),
    )


def admin_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving valid ``GOLDY_ADMIN_*`` values; override any key."""
    return StubSourceFactory.mirroring(
        AdminEnvSourceFactory(),
        admin_env(**overrides),
    )


def catalog_source_stub(**overrides: str) -> StubSourceFactory:
    """In-memory stub serving a valid default price type; override any key."""
    return StubSourceFactory.mirroring(
        CatalogEnvSourceFactory(),
        catalog_env(**overrides),
    )
