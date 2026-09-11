"""Who learns about a new order, and who deliberately does not.

The decisions under test are the ones a queue cannot make for us: which people
a new order is announced to, that a redelivered message announces it once, and
that one unreachable manager does not cost the others their message. Nothing
here touches FastStream — the consumer's whole job is to turn a body into a
command, and everything interesting happens after that.
"""

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.notify_order_placed.handler import (
    NotifyOrderPlacedHandler,
)
from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.order import OrderView
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from goldy.infrastructure.errors import NotificationSendError
from tests.unit.factories.order_factories import make_order_view
from tests.unit.factories.shop_factories import ORDER_ID
from tests.unit.stubs.notifications import (
    InMemoryInboxGateway,
    RecordingNotificationSender,
)
from tests.unit.stubs.orders import StubOrderQueryGateway

from .conftest import (
    ADMIN_ACCOUNT,
    CUSTOMER_ACCOUNT,
    MANAGER_ACCOUNT,
    MESSAGE_ID,
    OTHER_MESSAGE_ID,
    UserSeeder,
)

CUSTOMER_ID = "11111111-1111-1111-1111-111111111111"
MANAGER_ID = "22222222-2222-2222-2222-222222222222"
ADMIN_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture(autouse=True)
def placed_order(orders: StubOrderQueryGateway) -> OrderView:
    """One card in the read model, which is where the notifier reads it from.

    Autouse because every test here needs the order to exist and only some of
    them care what is on it. The one that wants it gone empties the gateway.
    """
    view = make_order_view(customer_id=UserId(UUID(CUSTOMER_ID)))
    orders.cards[OrderId(view.id)] = view
    return view


def a_placement() -> NotifyOrderPlacedCommand:
    return NotifyOrderPlacedCommand(message_id=MESSAGE_ID, order_id=UUID(ORDER_ID))


async def test_a_new_order_reaches_managers_and_administrators(
    seed_user: UserSeeder,
    placed_order: OrderView,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT)

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 2
    assert {n.external_id for n in sender.sent} == {MANAGER_ACCOUNT, ADMIN_ACCOUNT}
    assert placed_order.number in sender.text_to(MANAGER_ACCOUNT)


async def test_the_buyer_is_not_told_about_their_own_order(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """They pressed the button, and the screen already said so."""
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 0
    assert sender.sent == []


async def test_the_message_names_the_customer_the_address_and_the_total(
    seed_user: UserSeeder,
    placed_order: OrderView,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """The things a manager needs, none of which travelled in the event.

    ``OrderPlaced`` carries no address and no telephone number on purpose, so a
    message containing them is proof the handler read the order by its id
    rather than unpacking the payload.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    await notify_order_placed.handle(a_placement())

    text = sender.text_to(MANAGER_ACCOUNT)
    assert placed_order.delivery_address in text
    assert placed_order.recipient_phone_number in text
    assert placed_order.recipient_first_name in text
    assert f"{placed_order.total.amount:.2f}" in text


async def test_the_same_message_delivered_twice_is_announced_once(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """At-least-once delivery, stated as the thing the inbox has to survive.

    The relay marks an outbox row processed only after the transport accepted
    it, so a crash in between publishes the same row again — with the same id,
    which is the whole reason the key is the row's id and not a fresh one.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    first = await notify_order_placed.handle(a_placement())
    second = await notify_order_placed.handle(a_placement())

    assert first.delivered == 1
    assert second.already_handled
    assert second.delivered == 0
    assert len(sender.sent) == 1


async def test_a_second_message_about_the_same_order_is_still_delivered(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """The inbox refuses a repeated id, not a repeated subject.

    Worth pinning down because the two are easy to confuse, and keying off the
    order instead would silence every later fact about it.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    await notify_order_placed.handle(a_placement())
    second = await notify_order_placed.handle(
        NotifyOrderPlacedCommand(message_id=OTHER_MESSAGE_ID, order_id=UUID(ORDER_ID)),
    )

    assert second.delivered == 1
    assert len(sender.sent) == 2


async def test_a_blocked_manager_is_not_written_to(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """Blocking is the shop deciding to stop dealing with somebody.

    It applies to what we send them as much as to what they may do, and a
    blocked account is not a reason to fail the message for everybody else.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT, blocked=True)
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT)

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 1
    assert outcome.skipped == 1
    assert {n.external_id for n in sender.sent} == {ADMIN_ACCOUNT}


async def test_a_manager_who_asked_for_max_is_not_reached_on_telegram(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """``UserPreferences.notify_via`` is respected rather than consulted.

    The Telegram id is on file and would deliver perfectly well; sending to it
    anyway would make the setting decorative.
    """
    seed_user(
        MANAGER_ID,
        UserRole.MANAGER,
        MANAGER_ACCOUNT,
        notify_via=MessengerPlatform.MAX,
    )

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 0
    assert outcome.skipped == 1
    assert sender.sent == []


async def test_a_manager_whose_chosen_platform_is_unlinked_is_skipped(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """Writing to whatever account is on file is worse than writing nothing."""
    seed_user(
        MANAGER_ID,
        UserRole.MANAGER,
        MANAGER_ACCOUNT,
        notify_via=MessengerPlatform.MAX,
        linked=MessengerPlatform.TELEGRAM,
    )

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.skipped == 1
    assert sender.sent == []


async def test_a_manager_who_blocked_the_bot_does_not_cost_the_others_theirs(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """Forbidden is an ordinary answer from Telegram, not an incident.

    Letting it raise would put the message back on the queue and announce the
    order a second time to everybody the batch had already reached.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT)
    sender.unreachable.add(MANAGER_ACCOUNT)

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 1
    assert outcome.skipped == 1
    assert {n.external_id for n in sender.sent} == {ADMIN_ACCOUNT}


async def test_the_bot_api_failing_is_not_swallowed(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """A timeout has to reach the consumer so the message is redelivered.

    The inbox claim is part of the same transaction, so a raised error takes it
    with it — which is what leaves the message free to be claimed again.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    sender.failure = NotificationSendError("telegram is having a moment")

    with pytest.raises(NotificationSendError):
        await notify_order_placed.handle(a_placement())

    assert sender.sent == []


async def test_an_order_that_is_gone_is_not_announced_and_is_not_retried(
    seed_user: UserSeeder,
    orders: StubOrderQueryGateway,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
    inbox: InMemoryInboxGateway,
) -> None:
    """Nothing to say, and saying it again next minute would not help.

    The claim stays, which is what stops the message coming back forever.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    orders.cards.clear()

    outcome = await notify_order_placed.handle(a_placement())

    assert outcome.delivered == 0
    assert sender.sent == []
    assert MESSAGE_ID in inbox.claimed


async def test_a_manager_reading_english_is_written_to_in_english(
    seed_user: UserSeeder,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """The reader picks the language, not the process doing the sending."""
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT, locale="en")
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT, locale="ru")

    await notify_order_placed.handle(a_placement())

    assert "New order" in sender.text_to(MANAGER_ACCOUNT)
    assert "Новый заказ" in sender.text_to(ADMIN_ACCOUNT)


async def test_the_total_keeps_its_kopecks(
    seed_user: UserSeeder,
    placed_order: OrderView,
    orders: StubOrderQueryGateway,
    notify_order_placed: NotifyOrderPlacedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """Formatted in Python rather than by Fluent's number formatter.

    The currency arrives as data and a Fluent function may take only literal
    arguments, so the amount is rendered before it reaches the message — from
    the ``Decimal`` the view carries, never through a float.
    """
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    priced = MoneyView(amount=Decimal("1234567.89"), currency="RUB")
    orders.cards[OrderId(placed_order.id)] = replace(placed_order, total=priced)

    await notify_order_placed.handle(a_placement())

    assert "1234567.89 RUB" in sender.text_to(MANAGER_ACCOUNT)
