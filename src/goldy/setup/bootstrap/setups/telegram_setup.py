import logging
from typing import Any, Final

from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseEventIsolation, BaseStorage, DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiogram_dialog import setup_dialogs
from aiogram_i18n import I18nMiddleware
from aiogram_i18n.cores import BaseCore, FluentRuntimeCore

from goldy.presentation.telegram.handlers import setup_all_dialogs, setup_all_handlers
from goldy.presentation.telegram.locale_manager import UserLocaleManager
from goldy.presentation.telegram.locales_path import LOCALES_PATH
from goldy.presentation.telegram.middlewares.auth_middleware import AuthMiddleware
from goldy.presentation.telegram.middlewares.timing_middleware import TimingMiddleware
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.telegram_config import TelegramConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)


def setup_telegram_bot_storage(
    telegram_config: TelegramConfig,
    redis_config: RedisConfig,
) -> BaseStorage:
    """Where a half-finished dialogue lives between updates.

    Memory storage is for running the bot with nothing but a token: it loses
    every conversation on restart, which is fine locally and unacceptable in
    production, where a deploy would drop everyone mid-order.
    """
    if not telegram_config.use_redis_storage:
        logger.warning("telegram: using memory storage — dialogues die on restart")
        return MemoryStorage()

    return RedisStorage.from_url(
        url=redis_config.fsm_uri,
        key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
    )


def setup_telegram_bot_event_isolation(
    telegram_config: TelegramConfig,
    redis_config: RedisConfig,
) -> BaseEventIsolation:
    """Stops one chat's updates being handled twice at once.

    Memory isolation only covers a single process, so the moment there is more
    than one replica it stops isolating anything — two rapid taps would land on
    two workers and both would act.
    """
    if not telegram_config.use_redis_event_isolation:
        logger.warning("telegram: memory event isolation — safe for one replica only")
        return SimpleEventIsolation()

    return RedisEventIsolation.from_url(url=redis_config.fsm_uri)


def setup_telegram_bot_i18n_core(telegram_config: TelegramConfig) -> BaseCore[Any]:
    """Loads the Fluent translations shipped inside the package.

    The path comes from ``importlib.resources``, not from the working
    directory: anything relative works until the service is installed as a
    wheel and then silently finds nothing.
    """
    logger.debug("telegram: loading locales from %s", LOCALES_PATH)

    return FluentRuntimeCore(
        path=LOCALES_PATH / "{locale}" / "LC_MESSAGES",
        default_locale=telegram_config.default_locale,
        use_isolating=telegram_config.use_i18n_isolation,
    )


def setup_telegram_bot_dispatcher(
    storage: BaseStorage,
    events_isolation: BaseEventIsolation,
) -> Dispatcher:
    return Dispatcher(storage=storage, events_isolation=events_isolation)


def setup_telegram_bot_middlewares(
    dp: Dispatcher,
    core: BaseCore[Any],
    telegram_config: TelegramConfig,
) -> None:
    """Registers the outer middlewares, in the only order that works.

    dishka first, because authentication needs the container to load anybody.
    Authentication second, because the language depends on which user was
    found. i18n last, reading that user out of the data the gate just filled in.

    Registered here rather than in the entry point so the ordering constraint
    lives next to the explanation of it — getting it wrong produces a bot that
    answers everyone in Russian and cannot say why.
    """
    logger.debug("telegram: registering middlewares")

    dp.update.outer_middleware(TimingMiddleware())
    dp.update.outer_middleware(AuthMiddleware(core))

    I18nMiddleware(
        core=core,
        manager=UserLocaleManager(default_locale=telegram_config.default_locale),
        default_locale=telegram_config.default_locale,
    ).setup(dispatcher=dp)


def setup_telegram_routes(dp: Dispatcher) -> None:
    setup_all_handlers(dp)
    setup_all_dialogs(dp)
    setup_dialogs(dp)
