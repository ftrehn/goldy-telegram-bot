"""One stub source per config, serving valid values keyed by env var name."""

from goldy.setup.bootstrap.sources.alchemy_env_source_factory import (
    SQLAlchemyEnvSourceFactory,
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
from tests.unit.factories.env_data_factories import (
    postgres_env,
    rabbitmq_env,
    redis_env,
    sqlalchemy_env,
    taskiq_env,
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
