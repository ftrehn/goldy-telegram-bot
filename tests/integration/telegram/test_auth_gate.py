"""The gate in front of everything, and what it refuses.

``AuthMiddleware`` is an outer middleware on ``dp.update``, so it runs before
any router is consulted — which is the whole reason it is a middleware and not a
filter: a router added next month is covered without anybody remembering to
cover it. That property only holds when the real dispatcher is assembled, which
is what these tests do.
"""

import pytest
from aiogram.methods import SendMessage

from goldy.domain.users.values.user_role import UserRole
from goldy.presentation.telegram.common import text_keys
from tests.integration.arrange import UserBlocker
from tests.integration.telegram.arrange import (
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.personas import a_stranger
from tests.integration.telegram.sent import SentCalls

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


async def test_a_stranger_asking_for_their_profile_is_turned_away(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Fail-closed: anything that is not the registration flow stops here."""
    await feed(a_stranger().says("/me"))

    assert sent.only(SendMessage).text == text(text_keys.AUTH_REGISTRATION_REQUIRED)


async def test_a_stranger_typing_nonsense_is_turned_away_too(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The fallback would otherwise answer, which tells a stranger the bot is live."""
    await feed(a_stranger().says("привет"))

    assert sent.only(SendMessage).text == text(text_keys.AUTH_REGISTRATION_REQUIRED)


async def test_a_blocked_person_is_refused(
    register_person: PersonRegistrar,
    block_user: UserBlocker,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    person = await register_person()
    await block_user(person.user_id, "Оскорблял поддержку")

    await feed(person.says("/me"))

    assert sent.only(SendMessage).text == text(text_keys.ERROR_BLOCKED)


async def test_a_blocked_person_is_stopped_before_the_handler_runs(
    register_person: PersonRegistrar,
    block_user: UserBlocker,
    feed: UpdateFeeder,
    sent: SentCalls,
) -> None:
    """The aggregate refuses them too, but only once a command reaches it.

    By then they have already been shown a profile they cannot act on, which is
    why the check is duplicated here. ``only`` is the assertion: one message,
    not a refusal followed by a dialog window.
    """
    person = await register_person()
    await block_user(person.user_id, "Оскорблял поддержку")

    await feed(person.says("/me"))

    assert len(sent.all(SendMessage)) == 1


async def test_a_registered_person_reaches_the_handler(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The gate is only interesting if it also lets the right people through."""
    person = await register_person()

    await feed(person.says("/help"))

    assert sent.only(SendMessage).text == text(text_keys.HELP_CUSTOMER)


async def test_a_customer_is_never_told_that_the_admin_side_exists(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Two messages rather than one with a conditional, for exactly this reason."""
    person = await register_person()

    await feed(person.says("/help"))

    assert "/admin" not in sent.only(SendMessage).text
    assert sent.only(SendMessage).text == text(text_keys.HELP_CUSTOMER)


async def test_staff_are_told(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    manager = await register_person(UserRole.MANAGER)

    await feed(manager.says("/help"))

    assert sent.only(SendMessage).text == text(text_keys.HELP_STAFF)


async def test_a_mistyped_command_gets_an_answer_rather_than_silence(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Silence from a bot is indistinguishable from the bot being down."""
    person = await register_person()

    await feed(person.says("/mee"))

    assert sent.only(SendMessage).text == text(text_keys.UNKNOWN_COMMAND)


async def test_the_bot_stays_quiet_in_a_group(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
) -> None:
    """Every router is private-only: an order carries a number and an address.

    Answering in a group would print one of those where the whole chat can read
    it, so the correct behaviour is to say nothing at all.
    """
    person = await register_person()

    await feed(person.says_in_a_group("/me"))

    assert sent.all(SendMessage) == ()
