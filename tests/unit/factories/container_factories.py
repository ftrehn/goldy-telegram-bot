"""Object mothers for the contexts the four containers are built from.

Everything a container needs that is *not* wired by a provider comes in as
context, and the entry points assemble that themselves. These mothers assemble
the same shapes without reading the environment, so a test can build a
container in a process that has no Postgres, no broker and no bot token.

The runtime objects are real library classes rather than hand-written doubles,
and cheap ones on purpose: ``InMemoryBroker`` and ``LabelScheduleSource`` open
no connection when constructed, and neither does a ``RabbitBroker`` or an
aiogram ``Bot``. What a container build needs from them is only that they *are*
what the context key promises.
"""

from aiogram import Bot
from faststream.rabbit import RabbitBroker
from taskiq import AsyncBroker, InMemoryBroker, ScheduleSource
from taskiq.schedule_sources import LabelScheduleSource

from goldy.setup.bootstrap.setups.configs_setup import (
    SharedConfigs,
    make_telegram_container_context,
    make_worker_container_context,
)
from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.catalog_config import CatalogConfig
from goldy.setup.configs.notification_config import NotificationConfig
from goldy.setup.configs.taskiq_config import TaskIQConfig
from goldy.setup.configs.telegram_config import TelegramConfig
from tests.unit.factories.config_factories import (
    create_postgres_config,
    create_rabbitmq_config,
    create_redis_config,
)

VALID_SHAPED_BOT_TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
"""Never a real token — aiogram refuses to build a ``Bot`` from a bad shape."""


def create_shared_configs(
    *,
    default_price_type_id: str = "retail",
    admin_phone_numbers: str = "",
) -> SharedConfigs:
    """Object mother for the bundle every process is handed at startup."""
    return SharedConfigs(
        postgres=create_postgres_config(),
        alchemy=SQLAlchemyConfig(
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
            echo=False,
        ),
        redis=create_redis_config(),
        rabbitmq=create_rabbitmq_config(),
        taskiq=TaskIQConfig(),
        admin=AdminConfig(phone_numbers=admin_phone_numbers),
        catalog=CatalogConfig(default_price_type_id=default_price_type_id),
    )


def create_telegram_context() -> dict[type, object]:
    """The context ``goldy.telegram_bot`` hands its container."""
    return make_telegram_container_context(
        create_shared_configs(),
        TelegramConfig(bot_token=VALID_SHAPED_BOT_TOKEN),
        Bot(token=VALID_SHAPED_BOT_TOKEN),
    )


def create_worker_context() -> dict[type, object]:
    """The context ``goldy.worker_app`` hands its container.

    The notification config carries the same shaped-but-fake token the bot
    context uses. Nothing constructs a ``Bot`` while the container is merely
    built — the factory is ``APP``-scoped and lazy — but the key has to be in
    the context or the worker graph has no token to resolve and the build
    fails, which is precisely the wiring these contexts exist to exercise.
    """
    broker: AsyncBroker = InMemoryBroker()
    schedule_source: ScheduleSource = LabelScheduleSource(broker)
    return make_worker_container_context(
        create_shared_configs(),
        broker,
        schedule_source,
        RabbitBroker(),
        NotificationConfig(bot_token=VALID_SHAPED_BOT_TOKEN),
    )


def create_catalog_seed_context() -> dict[type, object]:
    """The context ``goldy.catalog_seed_app`` hands its container.

    The configs and nothing else. The snapshot path belongs to one run rather
    than to the process, so ``seed_catalog`` contributes it when it opens the
    request scope.
    """
    return create_shared_configs().as_context()
