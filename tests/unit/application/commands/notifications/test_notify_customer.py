"""What the buyer is told about their own order, and in which language.

Two commands, one audience. Both are answered from the event alone — the
number, the status, the reason, the two addresses are all it carries — so the
decisions left to test are the same ones every notification has: the right
person, the right language, silence where silence is correct, and exactly one
message per fact however many times the broker delivers it.
"""

from uuid import UUID

import pytest

from goldy.application.commands.notifications.notify_order_address.command import (
    NotifyDeliveryAddressChangedCommand,
)
from goldy.application.commands.notifications.notify_order_address.handler import (
    NotifyDeliveryAddressChangedHandler,
)
from goldy.application.commands.notifications.notify_order_status.command import (
    NotifyOrderStatusChangedCommand,
)
from goldy.application.commands.notifications.notify_order_status.handler import (
    NotifyOrderStatusChangedHandler,
)
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_role import UserRole
from goldy.infrastructure.errors import NotificationSendError
from tests.unit.stubs.notifications import (
    InMemoryInboxGateway,
    RecordingNotificationSender,
)

from .conftest import CUSTOMER_ACCOUNT, MESSAGE_ID, OTHER_MESSAGE_ID, UserSeeder

CUSTOMER_ID = "11111111-1111-1111-1111-111111111111"
UNKNOWN_ID = "99999999-9999-9999-9999-999999999999"
ORDER_NUMBER = "1042"
CANCELLATION_REASON = "Товара нет на складе"
OLD_ADDRESS = "Москва, Ленина 1"
NEW_ADDRESS = "Санкт-Петербург, Невский 20, кв. 3"


def a_status_change(
    status: OrderStatus = OrderStatus.SHIPPED,
    reason: str | None = None,
    customer_id: str = CUSTOMER_ID,
) -> NotifyOrderStatusChangedCommand:
    return NotifyOrderStatusChangedCommand(
        message_id=MESSAGE_ID,
        order_number=ORDER_NUMBER,
        customer_id=UUID(customer_id),
        new_status=status.value,
        reason=reason,
    )


def an_address_change(
    customer_id: str = CUSTOMER_ID,
) -> NotifyDeliveryAddressChangedCommand:
    return NotifyDeliveryAddressChangedCommand(
        message_id=OTHER_MESSAGE_ID,
        order_number=ORDER_NUMBER,
        customer_id=UUID(customer_id),
        old_address=OLD_ADDRESS,
        new_address=NEW_ADDRESS,
    )


async def test_the_buyer_learns_their_order_shipped(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    outcome = await notify_status_changed.handle(a_status_change())

    assert outcome.delivered == 1
    text = sender.text_to(CUSTOMER_ACCOUNT)
    assert ORDER_NUMBER in text
    assert "отгружен" in text


async def test_a_cancellation_carries_the_reason(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """The one transition whose explanation the customer is owed.

    Two message keys rather than one with a selector: a selector still has to
    be handed ``reason`` on every render, and Fluent raises on an argument it
    expects and does not get.
    """
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    await notify_status_changed.handle(
        a_status_change(OrderStatus.CANCELLED, CANCELLATION_REASON),
    )

    text = sender.text_to(CUSTOMER_ACCOUNT)
    assert "отменён" in text
    assert CANCELLATION_REASON in text


async def test_a_status_change_without_a_reason_says_nothing_about_one(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    await notify_status_changed.handle(a_status_change(OrderStatus.CONFIRMED))

    assert "Причина" not in sender.text_to(CUSTOMER_ACCOUNT)


async def test_an_unknown_status_is_printed_rather_than_guessed(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """1C can invent a status this build has never heard of.

    The Fluent selector's ``*[other]`` branch prints it as it came, which is
    unhelpful but honest — claiming the order is "new" would not be.
    """
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    await notify_status_changed.handle(
        NotifyOrderStatusChangedCommand(
            message_id=MESSAGE_ID,
            order_number=ORDER_NUMBER,
            customer_id=UUID(CUSTOMER_ID),
            new_status="awaiting_pickup",
            reason=None,
        ),
    )

    assert "awaiting_pickup" in sender.text_to(CUSTOMER_ACCOUNT)


async def test_the_same_status_message_twice_is_sent_once(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    await notify_status_changed.handle(a_status_change())
    second = await notify_status_changed.handle(a_status_change())

    assert second.already_handled
    assert len(sender.sent) == 1


async def test_a_blocked_customer_is_not_written_to(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
    inbox: InMemoryInboxGateway,
) -> None:
    """Blocked and silent, and the message is still marked handled.

    Redelivering would not change the answer — they are still blocked — so the
    claim stays and the queue moves on.
    """
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT, blocked=True)

    outcome = await notify_status_changed.handle(a_status_change())

    assert outcome.delivered == 0
    assert outcome.skipped == 1
    assert sender.sent == []
    assert MESSAGE_ID in inbox.claimed


async def test_a_customer_who_asked_for_max_is_not_reached_on_telegram(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(
        CUSTOMER_ID,
        UserRole.CUSTOMER,
        CUSTOMER_ACCOUNT,
        notify_via=MessengerPlatform.MAX,
    )

    outcome = await notify_status_changed.handle(a_status_change())

    assert outcome.skipped == 1
    assert sender.sent == []


async def test_an_order_belonging_to_nobody_is_skipped_not_retried(
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
    inbox: InMemoryInboxGateway,
) -> None:
    """A customer we cannot find will not be found next time either."""
    outcome = await notify_status_changed.handle(a_status_change(customer_id=UNKNOWN_ID))

    assert outcome.delivered == 0
    assert sender.sent == []
    assert MESSAGE_ID in inbox.claimed


async def test_the_bot_api_failing_reaches_the_consumer(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)
    sender.failure = NotificationSendError("telegram is having a moment")

    with pytest.raises(NotificationSendError):
        await notify_status_changed.handle(a_status_change())


async def test_an_english_speaking_buyer_reads_english(
    seed_user: UserSeeder,
    notify_status_changed: NotifyOrderStatusChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT, locale="en")

    await notify_status_changed.handle(a_status_change())

    assert "shipped" in sender.text_to(CUSTOMER_ACCOUNT)


async def test_a_corrected_address_is_confirmed_with_both_addresses(
    seed_user: UserSeeder,
    notify_address_changed: NotifyDeliveryAddressChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    """Was and now, both of them, because one alone says nothing.

    The aggregate keeps only the new address, which is why this is the one
    event allowed to carry one at all.
    """
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    outcome = await notify_address_changed.handle(an_address_change())

    assert outcome.delivered == 1
    text = sender.text_to(CUSTOMER_ACCOUNT)
    assert OLD_ADDRESS in text
    assert NEW_ADDRESS in text
    assert ORDER_NUMBER in text


async def test_the_same_address_message_twice_is_sent_once(
    seed_user: UserSeeder,
    notify_address_changed: NotifyDeliveryAddressChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)

    await notify_address_changed.handle(an_address_change())
    second = await notify_address_changed.handle(an_address_change())

    assert second.already_handled
    assert len(sender.sent) == 1


async def test_a_blocked_customer_is_not_told_about_the_address_either(
    seed_user: UserSeeder,
    notify_address_changed: NotifyDeliveryAddressChangedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT, blocked=True)

    outcome = await notify_address_changed.handle(an_address_change())

    assert outcome.skipped == 1
    assert sender.sent == []
