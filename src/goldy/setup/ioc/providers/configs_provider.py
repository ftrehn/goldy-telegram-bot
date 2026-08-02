from typing import Final

from dishka import Provider, Scope

from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.postgres_config import PostgresConfig
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.taskiq_config import TaskIQConfig


def configs_provider() -> Provider:
    """Supplies every configuration object from the container context.

    Configs are built once at startup by their loaders and handed to the
    container, rather than loaded here: reading the environment is a bootstrap
    decision, and a container that read it itself could not be built for a test.

    ``TelegramConfig`` is deliberately absent — only the bot process has one,
    so it is contributed by that process's own provider and a worker cannot
    accidentally depend on it.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.from_context(provides=PostgresConfig)
    provider.from_context(provides=SQLAlchemyConfig)
    provider.from_context(provides=RedisConfig)
    provider.from_context(provides=RabbitMQConfig)
    provider.from_context(provides=TaskIQConfig)
    provider.from_context(provides=AdminConfig)
    return provider
