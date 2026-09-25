"""Telling staff the site refused an order handed over to it (ADR-0004).

The order stays in the bot; nobody but the people who work orders needs to
know it will not reach the site or 1C on its own any more. The claim happens
before anything else, exactly as for every other notification, so a redelivery
does not announce the same refusal twice.
"""

from goldy.application.commands.notifications.notify_handover_rejected.command import (
    NotifyOrderHandoverRejectedCommand,
)
from goldy.application.commands.notifications.notify_handover_rejected.handler import (
    NotifyOrderHandoverRejectedHandler,
)
from goldy.application.common.events import OrderHandoverRejected
from goldy.domain.users.values.user_role import UserRole
from tests.unit.stubs.notifications import RecordingNotificationSender

from .conftest import (
    ADMIN_ACCOUNT,
    CUSTOMER_ACCOUNT,
    MANAGER_ACCOUNT,
    MESSAGE_ID,
    UserSeeder,
)

CUSTOMER_ID = "11111111-1111-1111-1111-111111111111"
MANAGER_ID = "22222222-2222-2222-2222-222222222222"
ADMIN_ID = "33333333-3333-3333-3333-333333333333"
ORDER_NUMBER = "240913-3K7QXA"


def a_rejection(code: str = "prices_changed") -> NotifyOrderHandoverRejectedCommand:
    return NotifyOrderHandoverRejectedCommand(
        message_id=MESSAGE_ID,
        event_type=OrderHandoverRejected.__name__,
        order_number=ORDER_NUMBER,
        code=code,
    )


async def test_only_staff_are_told_the_site_refused_an_order(
    seed_user: UserSeeder,
    notify_handover_rejected: NotifyOrderHandoverRejectedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(CUSTOMER_ID, UserRole.CUSTOMER, CUSTOMER_ACCOUNT)
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT)

    outcome = await notify_handover_rejected.handle(a_rejection())

    assert outcome.delivered == 2
    assert {n.external_id for n in sender.sent} == {MANAGER_ACCOUNT, ADMIN_ACCOUNT}


async def test_the_message_names_the_order_and_the_reason(
    seed_user: UserSeeder,
    notify_handover_rejected: NotifyOrderHandoverRejectedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    await notify_handover_rejected.handle(a_rejection("credit_limit_exceeded"))

    text = sender.text_to(MANAGER_ACCOUNT)
    assert ORDER_NUMBER in text
    assert "кредитного лимита" in text


async def test_an_unknown_site_code_is_printed_rather_than_guessed(
    seed_user: UserSeeder,
    notify_handover_rejected: NotifyOrderHandoverRejectedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    await notify_handover_rejected.handle(a_rejection("something_new"))

    assert "something_new" in sender.text_to(MANAGER_ACCOUNT)


async def test_a_redelivered_rejection_is_announced_once(
    seed_user: UserSeeder,
    notify_handover_rejected: NotifyOrderHandoverRejectedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT)

    first = await notify_handover_rejected.handle(a_rejection())
    second = await notify_handover_rejected.handle(a_rejection())

    assert first.delivered == 1
    assert second.already_handled
    assert len(sender.sent) == 1


async def test_a_blocked_manager_does_not_cost_the_administrator_theirs(
    seed_user: UserSeeder,
    notify_handover_rejected: NotifyOrderHandoverRejectedHandler,
    sender: RecordingNotificationSender,
) -> None:
    seed_user(MANAGER_ID, UserRole.MANAGER, MANAGER_ACCOUNT, blocked=True)
    seed_user(ADMIN_ID, UserRole.ADMIN, ADMIN_ACCOUNT)

    outcome = await notify_handover_rejected.handle(a_rejection())

    assert outcome.delivered == 1
    assert outcome.skipped == 1
    assert {n.external_id for n in sender.sent} == {ADMIN_ACCOUNT}
