import logging
from collections.abc import Mapping
from typing import Any, Final

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.base import BaseEventIsolation, BaseStorage, DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from aiogram_dialog import setup_dialogs
from aiogram_i18n import I18nMiddleware
from aiogram_i18n.cores import BaseCore, FluentRuntimeCore

from goldy.domain.users.values.locale import DEFAULT_LOCALE, SUPPORTED_LOCALES
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.locale_manager import UserLocaleManager
from goldy.presentation.telegram.common.locales_path import LOCALES_PATH
from goldy.presentation.telegram.handlers import setup_all_handlers
from goldy.presentation.telegram.middlewares.auth_middleware import AuthMiddleware
from goldy.presentation.telegram.middlewares.timing_middleware import TimingMiddleware
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.telegram_config import TelegramConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)

PUBLISHED_COMMANDS: Final[Mapping[str, str]] = {
    "catalog": text_keys.COMMAND_CATALOG,
    "search": text_keys.COMMAND_SEARCH,
    "cart": text_keys.COMMAND_CART,
    "orders": text_keys.COMMAND_ORDERS,
    "me": text_keys.COMMAND_ME,
    "help": text_keys.COMMAND_HELP,
}
"""The menu Telegram draws beside the text box, in the order it draws it.

Six commands and not seven. ``/manage_orders`` is deliberately absent, and its
absence is the whole reason this mapping is written out rather than derived
from the registered routers: ``help-staff`` exists so that a customer is never
told staff commands are there, and a menu published to every private chat would
walk straight around that. Staff reach the command by typing it, which is what
``/help`` tells them and only them.

``/start`` is missing for a different reason — Telegram offers it to anybody who
has not talked to the bot yet, and listing it again would put a command nobody
needs twice at the top of the menu.
"""


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


async def setup_bot_commands(bot: Bot, core: BaseCore[Any]) -> None:
    """Publishes the command menu, in every language the bot speaks.

    Scoped to ``BotCommandScopeAllPrivateChats`` because that is the only place
    the bot works at all — the chat-type filter on every router refuses a group
    — and because the scope is what keeps the staff command unpublished: there
    is no per-user list to maintain and nothing to forget to exclude.

    Published once per language plus once with no language at all. Telegram
    picks a localised menu by the client's own language setting and falls back
    to the unlabelled one, so without that last call a customer whose phone is
    set to German would see no menu rather than the shop's default.

    The core is started here rather than assumed started. The i18n middleware
    registers ``core.startup`` as a dispatcher startup hook, which has not run
    yet at the point a bot publishes its menu; loading the ``.ftl`` files twice
    costs milliseconds, and reading them zero times costs a ``KeyError`` in
    place of the menu.

    A refused publication is logged and survived rather than raised. The menu
    is a convenience and polling is not: making startup depend on an extra API
    call turns a minute of Telegram being unreachable into a deployment that
    cannot start, while the bot behind it would have served every command by
    name. A token that is actually wrong still stops the process — polling
    fails on it moments later, where the error says so plainly.
    """
    await core.startup()

    scope = BotCommandScopeAllPrivateChats()

    try:
        for locale in sorted(SUPPORTED_LOCALES):
            await bot.set_my_commands(
                commands=_commands_in(core, locale),
                scope=scope,
                language_code=locale,
            )

        await bot.set_my_commands(
            commands=_commands_in(core, core.default_locale or DEFAULT_LOCALE),
            scope=scope,
        )
    except TelegramAPIError:
        logger.warning("telegram: command menu not published", exc_info=True)
        return

    logger.info("telegram: published %d commands", len(PUBLISHED_COMMANDS))


def _commands_in(core: BaseCore[Any], locale: str) -> list[BotCommand]:
    """The menu worded in one language.

    Read straight from the Fluent core rather than through ``I18nContext``:
    there is no update being handled here and so no context to read, which is
    the same reason the auth gate renders its refusals this way.

    *locale* is a ``str`` and not ``str | None``, even though that is what
    ``BaseCore.get`` accepts, because ``None`` does not mean "the default" —
    it means "read the language out of the ``I18nContext`` of the update being
    handled", and there is no update here. Passing it raises ``LookupError``
    on a bare ``ContextVar``, which names nothing and points at aiogram_i18n
    rather than at the menu. Narrowing the parameter is what makes the caller
    resolve ``core.default_locale``, itself optional, into a real language.
    """
    return [
        BotCommand(command=command, description=core.get(key, locale))
        for command, key in PUBLISHED_COMMANDS.items()
    ]


def setup_telegram_routes(dp: Dispatcher) -> None:
    """Attaches the routers, then the machinery the dialogs among them need.

    ``setup_dialogs`` last, and only last: it registers the middlewares that
    resolve a dialog context, and it has to see every dialog already attached.
    """
    setup_all_handlers(dp)
    setup_dialogs(dp)
