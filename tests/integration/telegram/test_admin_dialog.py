"""The admin dialog, and the two independent things guarding it.

The staff filter on the router is convenience: a customer who guesses
``/admin`` is told the command is unknown rather than being refused, because a
refusal confirms it exists. Authorization is the other one, checked inside every
command against the aggregate, where nothing in presentation can bypass it —
including a staff member who reached a screen they should not act from.

Both are only real when the whole dispatcher is assembled, which is why they are
tested here and not against the handlers.
"""

import pytest
from aiogram.methods import SendMessage
from dishka import FromDishka

from goldy.application.common.ports.users import UserQueryGateway
from goldy.domain.users.values.user_role import UserRole
from goldy.presentation.telegram.common import text_keys
from tests.integration.inject import inject
from tests.integration.telegram.arrange import (
    ButtonPresser,
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.sent import SentCalls

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

BLOCK_REASON = "Оскорблял поддержку"


async def test_a_customer_is_told_the_command_does_not_exist(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Not "forbidden" — that would confirm there is an admin side to find."""
    customer = await register_person()

    await feed(customer.says("/admin"))

    assert sent.only(SendMessage).text == text(text_keys.UNKNOWN_COMMAND)


async def test_an_administrator_sees_everybody(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()

    await feed(admin.says("/admin"))

    assert sent.last(SendMessage).text == text(
        text_keys.ADMIN_USERS_TITLE,
        page=1,
        pages=1,
        total=2,
    )
    assert customer.list_label in sent.buttons()


async def test_opening_a_card_shows_that_person(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))

    await press(admin, customer.list_label)

    assert sent.last_text() == text(
        text_keys.ADMIN_USER_CARD,
        name=customer.list_label,
        phone=customer.phone_number,
        role="customer",
        status="active",
        locale="ru",
        reason="",
    )


@inject
async def test_an_administrator_blocks_a_customer_with_a_reason(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """The reason is on the record so whoever unblocks them knows why."""
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))
    await press(admin, customer.list_label)

    await press(admin, text(text_keys.ADMIN_BLOCK_BUTTON))
    await feed(admin.says(BLOCK_REASON))

    view = await users.read_by_id(customer.user_id)
    assert view is not None
    assert view.is_blocked is True
    assert view.block_reason == BLOCK_REASON


async def test_a_blocked_customer_is_turned_away_on_their_next_message(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The block only means something if the gate acts on it."""
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))
    await press(admin, customer.list_label)
    await press(admin, text(text_keys.ADMIN_BLOCK_BUTTON))
    await feed(admin.says(BLOCK_REASON))

    await feed(customer.says("/me"))

    assert sent.last_text() == text(text_keys.ERROR_BLOCKED)


@inject
async def test_unblocking_clears_the_reason(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """A stale reason on an active account reads as a block that never lifted."""
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))
    await press(admin, customer.list_label)
    await press(admin, text(text_keys.ADMIN_BLOCK_BUTTON))
    await feed(admin.says(BLOCK_REASON))

    await press(admin, text(text_keys.ADMIN_UNBLOCK_BUTTON))

    view = await users.read_by_id(customer.user_id)
    assert view is not None
    assert view.is_blocked is False
    assert view.block_reason is None


@inject
async def test_an_administrator_promotes_a_customer_to_manager(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))
    await press(admin, customer.list_label)

    await press(admin, text(text_keys.ADMIN_ROLE_BUTTON))
    await press(admin, UserRole.MANAGER.value)

    view = await users.read_by_id(customer.user_id)
    assert view is not None
    assert view.role == UserRole.MANAGER.value


async def test_the_role_screen_does_not_offer_administrator(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Nobody outranks an administrator, so granting one would always be refused.

    The first ones are seeded from configuration, which is the only way the role
    can exist at all.
    """
    admin = await register_person(UserRole.ADMIN)
    customer = await register_person()
    await feed(admin.says("/admin"))
    await press(admin, customer.list_label)

    await press(admin, text(text_keys.ADMIN_ROLE_BUTTON))

    assert UserRole.ADMIN.value not in sent.buttons()
    assert UserRole.MANAGER.value in sent.buttons()


@inject
async def test_a_manager_cannot_block_a_peer(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """The screen lets them try; the aggregate is what stops them.

    Managers are subordinate to administrators and to nobody else, so a manager
    reaching another manager's card gets as far as typing a reason and no
    further — which is exactly the case a filter on the router cannot cover.
    """
    manager = await register_person(UserRole.MANAGER)
    peer = await register_person(UserRole.MANAGER)
    await feed(manager.says("/admin"))
    await press(manager, peer.list_label)

    await press(manager, text(text_keys.ADMIN_BLOCK_BUTTON))
    await feed(manager.says(BLOCK_REASON))

    assert sent.last_text() == text(text_keys.ERROR_FORBIDDEN)
    view = await users.read_by_id(peer.user_id)
    assert view is not None
    assert view.is_blocked is False


@inject
async def test_an_administrator_cannot_block_themselves(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """Falls out of the hierarchy table rather than needing a rule of its own.

    Nobody is their own subordinate, so the same check that stops an
    administrator blocking a peer stops them blocking themselves.
    """
    admin = await register_person(UserRole.ADMIN)
    await feed(admin.says("/admin"))
    await press(admin, admin.list_label)

    await press(admin, text(text_keys.ADMIN_BLOCK_BUTTON))
    await feed(admin.says(BLOCK_REASON))

    assert sent.last_text() == text(text_keys.ERROR_FORBIDDEN)
    view = await users.read_by_id(admin.user_id)
    assert view is not None
    assert view.is_blocked is False


async def test_an_empty_list_says_so(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Only the administrator exists, so the page is them and nothing else."""
    admin = await register_person(UserRole.ADMIN)

    await feed(admin.says("/admin"))

    assert sent.buttons() == (admin.list_label, text(text_keys.ADMIN_CLOSE_BUTTON))
