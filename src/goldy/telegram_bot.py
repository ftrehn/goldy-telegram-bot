import asyncio
import logging
from typing import Final

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dishka.integrations.aiogram import setup_dishka
from sqlalchemy.orm import clear_mappers

from goldy.setup.bootstrap.setups.admin_setup import seed_admins
from goldy.setup.bootstrap.setups.configs_setup import (
    load_shared_configs,
    load_telegram_config,
    make_telegram_container_context,
)
from goldy.setup.bootstrap.setups.database_setup import setup_map_tables
from goldy.setup.bootstrap.setups.logging_setup import configure_logging
from goldy.setup.bootstrap.setups.telegram_setup import (
    setup_telegram_bot_dispatcher,
    setup_telegram_bot_event_isolation,
    setup_telegram_bot_i18n_core,
    setup_telegram_bot_middlewares,
    setup_telegram_bot_storage,
    setup_telegram_routes,
)
from goldy.setup.configs.logging_config import LoggingConfig
from goldy.setup.ioc.containers import make_telegram_container

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def create_bot() -> None:
    """Builds every part of the bot, in the order their dependencies allow."""
    configure_logging(LoggingConfig())

    configs = load_shared_configs()
    telegram_config = load_telegram_config()

    setup_map_tables()

    bot = Bot(
        token=telegram_config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp: Dispatcher = setup_telegram_bot_dispatcher(
        storage=setup_telegram_bot_storage(telegram_config, configs.redis),
        events_isolation=setup_telegram_bot_event_isolation(
            telegram_config,
            configs.redis,
        ),
    )

    container = make_telegram_container(
        make_telegram_container_context(configs, telegram_config, bot),
    )

    # Before our own middlewares, so authentication has a container to resolve
    # the gateway from — dishka registers an outer middleware of its own, and
    # middlewares run in registration order.
    setup_dishka(container=container, router=dp, auto_inject=True)

    setup_telegram_bot_middlewares(
        dp,
        setup_telegram_bot_i18n_core(telegram_config),
        telegram_config,
    )
    setup_telegram_routes(dp)

    await seed_admins(container)

    try:
        await bot.delete_webhook(
            drop_pending_updates=telegram_config.drop_pending_updates,
        )
        await dp.start_polling(bot)
    finally:
        await container.close()
        clear_mappers()


def main() -> None:
    try:
        asyncio.run(create_bot())
    except KeyboardInterrupt, SystemExit:
        logger.info("the bot was turned off")


if __name__ == "__main__":
    main()
