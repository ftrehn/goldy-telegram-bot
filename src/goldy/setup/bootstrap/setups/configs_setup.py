import logging
from dataclasses import dataclass
from typing import Final

from aiogram import Bot
from faststream.rabbit import RabbitBroker
from taskiq import AsyncBroker, ScheduleSource

from goldy.setup.bootstrap.loaders.admin_config_loader import AdminConfigLoader
from goldy.setup.bootstrap.loaders.alchemy_config_loader import SQLAlchemyConfigLoader
from goldy.setup.bootstrap.loaders.postgres_config_loader import PostgresConfigLoader
from goldy.setup.bootstrap.loaders.rabbitmq_config_loader import RabbitMQConfigLoader
from goldy.setup.bootstrap.loaders.redis_config_loader import RedisConfigLoader
from goldy.setup.bootstrap.loaders.taskiq_config_loader import TaskIQConfigLoader
from goldy.setup.bootstrap.loaders.telegram_config_loader import TelegramConfigLoader
from goldy.setup.bootstrap.sources.admin_env_source_factory import AdminEnvSourceFactory
from goldy.setup.bootstrap.sources.alchemy_env_source_factory import (
    SQLAlchemyEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.postgres_env_source_factory import (
    PostgresEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.rabbitmq_env_source_factory import (
    RabbitMQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.redis_env_source_factory import RedisEnvSourceFactory
from goldy.setup.bootstrap.sources.taskiq_env_source_factory import (
    TaskIQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.telegram_env_source_factory import (
    TelegramEnvSourceFactory,
)
from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.postgres_config import PostgresConfig
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.taskiq_config import TaskIQConfig
from goldy.setup.configs.telegram_config import TelegramConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SharedConfigs:
    """Every setting both processes need, loaded once at startup.

    A typed bundle rather than the ``dict[type, object]`` the container wants:
    an entry point that reaches for ``configs[RedisConfig]`` gets an ``object``
    back and every use of it becomes a cast. Here the fields keep their types
    and :meth:`as_context` does the widening in one place, where it belongs.
    """

    postgres: PostgresConfig
    alchemy: SQLAlchemyConfig
    redis: RedisConfig
    rabbitmq: RabbitMQConfig
    taskiq: TaskIQConfig
    admin: AdminConfig

    def as_context(self) -> dict[type, object]:
        """Keys these by the type the container provides them as."""
        return {
            PostgresConfig: self.postgres,
            SQLAlchemyConfig: self.alchemy,
            RedisConfig: self.redis,
            RabbitMQConfig: self.rabbitmq,
            TaskIQConfig: self.taskiq,
            AdminConfig: self.admin,
        }


def load_shared_configs() -> SharedConfigs:
    """Reads the environment for everything both processes need.

    Loaded here rather than inside the container so that a bad environment
    fails at startup with dature's own message, listing every offending
    variable at once — rather than on the first update that happens to need the
    setting nobody set.
    """
    logger.debug("configs: loading shared configuration")

    return SharedConfigs(
        postgres=PostgresConfigLoader(PostgresEnvSourceFactory()).load(),
        alchemy=SQLAlchemyConfigLoader(SQLAlchemyEnvSourceFactory()).load(),
        redis=RedisConfigLoader(RedisEnvSourceFactory()).load(),
        rabbitmq=RabbitMQConfigLoader(RabbitMQEnvSourceFactory()).load(),
        taskiq=TaskIQConfigLoader(TaskIQEnvSourceFactory()).load(),
        admin=AdminConfigLoader(AdminEnvSourceFactory()).load(),
    )


def load_telegram_config() -> TelegramConfig:
    """Read only by the bot process — a worker has no token and needs none."""
    return TelegramConfigLoader(TelegramEnvSourceFactory()).load()


def make_worker_container_context(
    configs: SharedConfigs,
    broker: AsyncBroker,
    schedule_source: ScheduleSource,
    event_broker: RabbitBroker,
) -> dict[type, object]:
    """The context the worker's container is built from.

    The three runtime objects cannot come from the container: the broker has to
    exist before tasks are registered on it, and the container is what the
    tasks resolve their dependencies from.
    """
    return {
        **configs.as_context(),
        AsyncBroker: broker,
        ScheduleSource: schedule_source,
        RabbitBroker: event_broker,
    }


def make_telegram_container_context(
    configs: SharedConfigs,
    telegram_config: TelegramConfig,
    bot: Bot,
) -> dict[type, object]:
    """The context the bot's container is built from.

    The ``Bot`` is here for the same reason: aiogram needs it to build the
    dispatcher, which is then wired to the container it could not have come
    from.
    """
    return {
        **configs.as_context(),
        TelegramConfig: telegram_config,
        Bot: bot,
    }
