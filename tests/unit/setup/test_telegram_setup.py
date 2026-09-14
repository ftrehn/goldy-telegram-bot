import logging
from collections.abc import AsyncGenerator
from typing import Any, Final, cast, override

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SetMyCommands, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram_i18n.cores import FluentRuntimeCore

from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.presentation.telegram.common.locales_path import LOCALES_PATH
from goldy.setup.bootstrap.setups.telegram_setup import (
    PUBLISHED_COMMANDS,
    setup_bot_commands,
)

TOKEN: Final[str] = "123456789:AAEy_thisTokenIsNeverSentAnywhere_xxxx"


class _RecordingSession(BaseSession):
    """A transport that answers instead of Telegram, and remembers what it was asked.

    A real ``Bot`` over a stub session rather than a stub bot: the parameter is
    typed ``Bot`` and the project forbids silencing a type checker, so the way
    to test the call is to replace what the call travels over.
    """

    ACCEPTED: Final[bool] = True
    """What Telegram answers ``setMyCommands`` with when it accepts one."""

    def __init__(self, *, refuse: bool = False) -> None:
        super().__init__()
        self.refuse: Final[bool] = refuse
        self.calls: list[TelegramMethod[Any]] = []

    @override
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.calls.append(method)

        if self.refuse:
            raise TelegramAPIError(method=method, message="Bad Gateway")

        return cast("TelegramType", self.ACCEPTED)

    @override
    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes]:
        yield b""

    @override
    async def close(self) -> None:
        return None


def _core() -> FluentRuntimeCore:
    return FluentRuntimeCore(path=LOCALES_PATH, default_locale=DEFAULT_LOCALE)


async def test_unreachable_telegram_does_not_stop_the_bot_from_starting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The menu is a convenience; polling is the bot.

    Publishing the menu is an extra API call, and letting that call decide
    whether the process starts turns a minute of Telegram being unreachable
    into a deployment that cannot come up - while the bot behind it would have
    served every command typed by name.
    """
    session = _RecordingSession(refuse=True)
    bot = Bot(token=TOKEN, session=session)

    with caplog.at_level(logging.WARNING):
        await setup_bot_commands(bot, _core())

    assert len(session.calls) == 1
    assert "command menu not published" in caplog.text


async def test_menu_is_published_once_per_language_and_once_without_one() -> None:
    """A client set to a language we do not speak still gets a menu.

    Telegram picks a localised menu by the client's own language and falls back
    to the unlabelled one, which is why the last call carries no language code.
    """
    session = _RecordingSession()
    bot = Bot(token=TOKEN, session=session)

    await setup_bot_commands(bot, _core())

    assert len(session.calls) == 3
    assert all(
        len(call.commands) == len(PUBLISHED_COMMANDS)
        for call in session.calls
        if isinstance(call, SetMyCommands)
    )


async def test_the_staff_command_is_never_published() -> None:
    """``help-staff`` exists so a customer is not told the command exists.

    A menu that published ``/manage_orders`` would hand every customer the
    thing the split help was written to withhold.
    """
    session = _RecordingSession()
    bot = Bot(token=TOKEN, session=session)

    await setup_bot_commands(bot, _core())

    published = {
        command.command
        for call in session.calls
        if isinstance(call, SetMyCommands)
        for command in call.commands
    }

    assert "manage_orders" not in published
