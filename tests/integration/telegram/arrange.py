"""Signatures of the Telegram-side fixtures.

Beside them rather than inside ``conftest.py`` so a test can name what it
depends on without importing a conftest, which pytest owns.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from aiogram.types import Update

from goldy.domain.users.values.user_role import UserRole
from tests.integration.telegram.personas import Person

type UpdateFeeder = Callable[[Update], Awaitable[None]]
type TextRenderer = Callable[..., str]
type ButtonPresser = Callable[[Person, str], Awaitable[None]]


class PersonRegistrar(Protocol):
    """Puts somebody in the database and hands back who they are on Telegram."""

    async def __call__(
        self,
        role: UserRole = UserRole.CUSTOMER,
        phone_number: str | None = None,
    ) -> Person: ...
