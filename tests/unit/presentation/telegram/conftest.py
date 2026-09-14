from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiogram_i18n import I18nContext
from aiogram_i18n.cores import BaseCore

from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.presentation.telegram.common.locale_manager import UserLocaleManager
from goldy.setup.bootstrap.setups.telegram_setup import setup_telegram_bot_i18n_core
from goldy.setup.configs.telegram_config import TelegramConfig


@pytest.fixture()
async def i18n_core() -> AsyncIterator[BaseCore[Any]]:
    """The real Fluent core, over the ``.ftl`` files shipped in the package.

    Built through the production factory rather than by hand, because half of
    what can go wrong with translations is where they are looked for: the path
    comes from ``importlib.resources``, and a test that reassembled it would
    keep passing after the real one broke.

    Isolation is off so that assertions compare against the text a person sees
    instead of against the same text wrapped in the Unicode direction marks
    Fluent inserts around every placeable.
    """
    core = setup_telegram_bot_i18n_core(
        TelegramConfig(bot_token="1:test", use_i18n_isolation=False),
    )
    await core.startup()

    yield core

    await core.shutdown()


@pytest.fixture()
def russian(i18n_core: BaseCore[Any]) -> I18nContext:
    """An i18n context in the shop's own language, for the formatters."""
    return _context(i18n_core, DEFAULT_LOCALE)


def _context(core: BaseCore[Any], locale: str) -> I18nContext:
    return I18nContext(
        locale=locale,
        core=core,
        manager=UserLocaleManager(default_locale=DEFAULT_LOCALE),
        data={},
    )
