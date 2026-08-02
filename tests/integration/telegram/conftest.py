"""The bot as it actually runs, with a fake Telegram on the far side.

The dispatcher is built by the same ``setup_telegram_*`` functions the entry
point calls, in the same order — dishka, then the auth gate, then i18n, then the
routes. That order is load-bearing and undocumented anywhere but in the setup
module, so reproducing it here rather than assembling something simpler is the
whole point: these tests fail if it changes.

Everything below the dispatcher is real too. An update fed here reaches a
handler, which sends a command through the mediator, which opens a transaction,
writes to Postgres and drains its events into the outbox.
"""

from collections.abc import AsyncIterator, Iterator
from itertools import count
from typing import Any, Final

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram_i18n.cores import BaseCore
from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka

from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.domain.users.values.user_role import UserRole
from goldy.setup.bootstrap.setups.configs_setup import SharedConfigs
from goldy.setup.bootstrap.setups.telegram_setup import (
    setup_telegram_bot_dispatcher,
    setup_telegram_bot_event_isolation,
    setup_telegram_bot_i18n_core,
    setup_telegram_bot_middlewares,
    setup_telegram_bot_storage,
    setup_telegram_routes,
)
from goldy.setup.configs.telegram_config import TelegramConfig
from tests.integration.arrange import UserSeeder
from tests.integration.telegram.arrange import (
    ButtonPresser,
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.mocked_bot import RecordingBot
from tests.integration.telegram.personas import Person
from tests.integration.telegram.sent import SentCalls

FIRST_TELEGRAM_ID: Final[int] = 500_001

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="session")
def i18n_core(telegram_config: TelegramConfig) -> BaseCore[Any]:
    """The real Fluent core, reading the ``.ftl`` files shipped in the package.

    Real rather than stubbed because loading them has broken before — the
    locales directory turning into a package was enough to make every message
    come out as its own key, and nothing but loading them catches that.
    """
    return setup_telegram_bot_i18n_core(telegram_config)


@pytest.fixture(scope="session")
async def dispatcher(
    telegram_container: AsyncContainer,
    telegram_config: TelegramConfig,
    shared_configs: SharedConfigs,
    i18n_core: BaseCore[Any],
    bot: RecordingBot,
) -> AsyncIterator[Dispatcher]:
    """Session-scoped because a ``Router`` may only ever be attached once.

    ``PROFILE_DIALOG`` and ``ADMIN_DIALOG`` are module-level singletons, so a
    dispatcher per test would fail on the second one with "router is already
    attached". State that would otherwise leak between tests is cleared by
    ``_forget_the_previous_test`` instead.

    ``emit_startup`` is not ceremony. ``I18nMiddleware.setup`` registers the
    Fluent core's loader on ``dispatcher.startup``, and ``setup_dialogs``
    registers one of its own — assembling the dispatcher without firing them
    leaves a bot whose every message raises ``KeyError`` on its own locale.
    Polling does this in production; a test that skipped it would be testing a
    dispatcher that has never actually started.
    """
    dp = setup_telegram_bot_dispatcher(
        storage=setup_telegram_bot_storage(telegram_config, shared_configs.redis),
        events_isolation=setup_telegram_bot_event_isolation(
            telegram_config,
            shared_configs.redis,
        ),
    )

    setup_dishka(container=telegram_container, router=dp, auto_inject=True)
    setup_telegram_bot_middlewares(dp, i18n_core, telegram_config)
    setup_telegram_routes(dp)

    await dp.emit_startup(bot=bot, dispatcher=dp)
    yield dp
    await dp.emit_shutdown(bot=bot, dispatcher=dp)


@pytest.fixture(autouse=True)
def _forget_the_previous_test(
    dispatcher: Dispatcher,
    bot: RecordingBot,
) -> Iterator[None]:
    """Clears the dialogue state and the recording around every test.

    Autouse because both outlive the session: without it a test could find
    itself already three screens into a dialog somebody else opened, or assert
    on a message the previous test's bot sent.
    """
    _reset(dispatcher, bot)
    yield
    _reset(dispatcher, bot)


def _reset(dispatcher: Dispatcher, bot: RecordingBot) -> None:
    storage = dispatcher.storage
    if isinstance(storage, MemoryStorage):
        storage.storage.clear()
    bot.recorded.forget()


@pytest.fixture()
def dishka_container(telegram_container: AsyncContainer) -> AsyncContainer:
    """Overrides the root fixture: here a test reads through the bot's container."""
    return telegram_container


@pytest.fixture()
def sent(bot: RecordingBot) -> SentCalls:
    """Everything the bot said while handling the updates this test fed."""
    return SentCalls(bot.recorded)


@pytest.fixture()
def feed(dispatcher: Dispatcher, bot: RecordingBot) -> UpdateFeeder:
    """Hands one update to the dispatcher, the way polling would."""

    async def _feed(update: Update) -> None:
        await dispatcher.feed_update(bot, update)

    return _feed


@pytest.fixture()
def text(i18n_core: BaseCore[Any]) -> TextRenderer:
    """Renders a Fluent key the way the bot renders it.

    Tests compare against this rather than against a Russian literal. Copying
    the wording in would mean a translation change breaks tests that have
    nothing to do with it, and a missing translation would go unnoticed because
    both sides would be wrong in the same way.

    The language is positional-only so it cannot collide with a placeholder of
    the same name — ``me-profile`` has one called ``locale``, and a keyword
    parameter would have swallowed it and rendered the message without it.
    """

    def render(key: str, language: str = DEFAULT_LOCALE, /, **placeholders: Any) -> str:
        return i18n_core.get(key, language, **placeholders)

    return render


@pytest.fixture()
def register_person(seed_user: UserSeeder) -> PersonRegistrar:
    """Somebody who has already registered, with the two ids kept in step.

    Each call gets its own Telegram id and its own number, so a test with an
    administrator and a customer in it cannot have them collide on the unique
    index and fail as "already exists".
    """
    telegram_ids = count(FIRST_TELEGRAM_ID)

    async def register(
        role: UserRole = UserRole.CUSTOMER,
        phone_number: str | None = None,
    ) -> Person:
        telegram_id = next(telegram_ids)
        number = phone_number if phone_number is not None else f"+79{telegram_id:09d}"

        user = await seed_user(
            phone_number=number,
            external_id=str(telegram_id),
            role=role,
        )

        return Person(
            user_id=user.id,
            telegram_id=telegram_id,
            phone_number=number,
        )

    return register


@pytest.fixture()
def press(feed: UpdateFeeder, sent: SentCalls) -> ButtonPresser:
    """Taps the button carrying this label on the window last shown.

    By label rather than by callback data: aiogram-dialog builds that data from
    widget ids, and a test naming it would be asserting on an implementation
    detail nobody looking at the bot can see.
    """

    async def _press(person: Person, label: str) -> None:
        callback_data = sent.callback_data_for(label)
        message_id = sent.last_message_id()
        await feed(person.presses(callback_data, message_id))

    return _press
