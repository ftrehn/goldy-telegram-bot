import logging
from dataclasses import dataclass
from typing import Final

from aiogram import Bot
from faststream.rabbit import RabbitBroker
from taskiq import AsyncBroker, ScheduleSource

from goldy.setup.bootstrap.loaders.admin_config_loader import AdminConfigLoader
from goldy.setup.bootstrap.loaders.alchemy_config_loader import SQLAlchemyConfigLoader
from goldy.setup.bootstrap.loaders.catalog_config_loader import CatalogConfigLoader
from goldy.setup.bootstrap.loaders.notification_config_loader import (
    NotificationConfigLoader,
)
from goldy.setup.bootstrap.loaders.postgres_config_loader import PostgresConfigLoader
from goldy.setup.bootstrap.loaders.rabbitmq_config_loader import RabbitMQConfigLoader
from goldy.setup.bootstrap.loaders.redis_config_loader import RedisConfigLoader
from goldy.setup.bootstrap.loaders.site_api_config_loader import SiteApiConfigLoader
from goldy.setup.bootstrap.loaders.taskiq_config_loader import TaskIQConfigLoader
from goldy.setup.bootstrap.loaders.telegram_config_loader import TelegramConfigLoader
from goldy.setup.bootstrap.sources.admin_env_source_factory import AdminEnvSourceFactory
from goldy.setup.bootstrap.sources.alchemy_env_source_factory import (
    SQLAlchemyEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.catalog_env_source_factory import (
    CatalogEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.notification_env_source_factory import (
    NotificationEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.postgres_env_source_factory import (
    PostgresEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.rabbitmq_env_source_factory import (
    RabbitMQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.redis_env_source_factory import RedisEnvSourceFactory
from goldy.setup.bootstrap.sources.site_api_env_source_factory import (
    SiteApiEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.taskiq_env_source_factory import (
    TaskIQEnvSourceFactory,
)
from goldy.setup.bootstrap.sources.telegram_env_source_factory import (
    TelegramEnvSourceFactory,
)
from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.catalog_config import CatalogConfig
from goldy.setup.configs.notification_config import NotificationConfig
from goldy.setup.configs.postgres_config import PostgresConfig
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.site_api_config import SiteApiConfig
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
    catalog: CatalogConfig

    def as_context(self) -> dict[type, object]:
        """Keys these by the type the container provides them as."""
        return {
            PostgresConfig: self.postgres,
            SQLAlchemyConfig: self.alchemy,
            RedisConfig: self.redis,
            RabbitMQConfig: self.rabbitmq,
            TaskIQConfig: self.taskiq,
            AdminConfig: self.admin,
            CatalogConfig: self.catalog,
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
        catalog=CatalogConfigLoader(CatalogEnvSourceFactory()).load(),
    )


def load_telegram_config() -> TelegramConfig:
    """Read only by the bot process — how *that* process is wired."""
    return TelegramConfigLoader(TelegramEnvSourceFactory()).load()


def load_notification_config() -> NotificationConfig:
    """Read only by the worker — the token it writes to people with.

    The same variable the bot reads, and a different object. The bot needs
    dialogue storage, event isolation and a default locale; the notifier needs
    a token and nothing else, and giving it the whole :class:`TelegramConfig`
    would put that object in the shared provider where every process could
    reach the secret.
    """
    return NotificationConfigLoader(NotificationEnvSourceFactory()).load()


def load_site_api_config() -> SiteApiConfig:
    """Read by the bot, the worker and the scheduler — how the site is reached.

    Kept out of :class:`SharedConfigs` all the same, because the seeder is a
    process too and has no business holding the site token. The bot needs it
    to link people, price them and read their finance (ADR-0004); the worker
    to pull the catalog and hand orders over; the scheduler because it builds
    the worker's broker, and the schedules are declared on that broker.
    """
    return SiteApiConfigLoader(SiteApiEnvSourceFactory()).load()


@dataclass(frozen=True, slots=True)
class WorkerConfigs:
    """The settings only the worker process holds, loaded by its entry point.

    A parameter object rather than two more arguments to
    :func:`make_worker_container_context`: both are secrets the worker alone
    carries, they travel together from the entry point to the container, and
    the next one — the MAX token — will join them here rather than grow the
    signature again.

    Attributes:
        notification: The Bot API token the worker writes to people with.
        site_api: How the worker reaches the site it pulls the catalog from.
    """

    notification: NotificationConfig
    site_api: SiteApiConfig


def load_worker_configs() -> WorkerConfigs:
    """Everything :class:`WorkerConfigs` holds, read from the environment."""
    return WorkerConfigs(
        notification=load_notification_config(),
        site_api=load_site_api_config(),
    )


def make_worker_container_context(
    configs: SharedConfigs,
    broker: AsyncBroker,
    schedule_source: ScheduleSource,
    event_broker: RabbitBroker,
    worker_configs: WorkerConfigs,
) -> dict[type, object]:
    """The context the worker's container is built from.

    The three runtime objects cannot come from the container: the broker has to
    exist before tasks are registered on it, and the container is what the
    tasks resolve their dependencies from.

    ``NotificationConfig`` and ``SiteApiConfig`` enter the same way
    ``TelegramConfig`` does for the bot — through the process that has them,
    never through the shared configs bundle. A worker without either fails to
    build its container at startup, which is the failure we want: the
    alternative is a worker that runs happily and is silent about every order,
    or never refreshes the catalog.
    """
    return {
        **configs.as_context(),
        AsyncBroker: broker,
        ScheduleSource: schedule_source,
        RabbitBroker: event_broker,
        NotificationConfig: worker_configs.notification,
        SiteApiConfig: worker_configs.site_api,
    }


def make_telegram_container_context(
    configs: SharedConfigs,
    telegram_config: TelegramConfig,
    bot: Bot,
    site_api_config: SiteApiConfig,
) -> dict[type, object]:
    """The context the bot's container is built from.

    The ``Bot`` is here for the same reason: aiogram needs it to build the
    dispatcher, which is then wired to the container it could not have come
    from. ``SiteApiConfig`` enters the way the worker's does — through the
    process that holds it — because the bot asks the site on a person's
    behalf: linking, personal prices, finance, cancelling a handed-over order.
    """
    return {
        **configs.as_context(),
        TelegramConfig: telegram_config,
        Bot: bot,
        SiteApiConfig: site_api_config,
    }
