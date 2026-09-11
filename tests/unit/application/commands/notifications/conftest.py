"""The notification handlers, assembled from the shared stubs.

The renderer is the real ``FluentNotificationRenderer`` rather than a stub, and
that is the point of these tests as much as the routing is. A Fluent message
whose argument is not passed does not degrade into visible text — it raises —
so a handler that forgot one is only caught by actually rendering what it
built. A recording stub would have happily accepted every call.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import pytest

from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_order_address.handler import (
    NotifyDeliveryAddressChangedHandler,
)
from goldy.application.commands.notifications.notify_order_placed.handler import (
    NotifyOrderPlacedHandler,
)
from goldy.application.commands.notifications.notify_order_status.handler import (
    NotifyOrderStatusChangedHandler,
)
from goldy.application.common.ports.notifications import NotificationRenderer
from goldy.application.common.views.user import MessengerAccountView, UserView
from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from goldy.infrastructure.adapters.notifications.fluent_notification_renderer import (
    FluentNotificationRenderer,
)
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_LOCALES_PATH,
)
from tests.unit.stubs.gateways import InMemoryUserQueryGateway
from tests.unit.stubs.notifications import (
    InMemoryInboxGateway,
    RecordingNotificationSender,
)
from tests.unit.stubs.orders import StubOrderQueryGateway

CUSTOMER_ACCOUNT: Final[str] = "1001"
MANAGER_ACCOUNT: Final[str] = "2002"
ADMIN_ACCOUNT: Final[str] = "3003"

MESSAGE_ID: Final[UUID] = UUID("aaaaaaaa-0000-0000-0000-000000000001")
OTHER_MESSAGE_ID: Final[UUID] = UUID("aaaaaaaa-0000-0000-0000-000000000002")

type UserSeeder = Callable[..., UserView]


@pytest.fixture(scope="session")
def renderer() -> NotificationRenderer:
    """The real translations, parsed once for the whole session.

    Session-scoped because parsing two ``.ftl`` files per test is the only
    expensive thing in this module, and the renderer holds no state between
    calls.
    """
    return FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH)


@pytest.fixture()
def inbox() -> InMemoryInboxGateway:
    return InMemoryInboxGateway()


@pytest.fixture()
def sender() -> RecordingNotificationSender:
    return RecordingNotificationSender()


@pytest.fixture()
def users() -> InMemoryUserQueryGateway:
    return InMemoryUserQueryGateway()


@pytest.fixture()
def orders() -> StubOrderQueryGateway:
    return StubOrderQueryGateway()


@pytest.fixture()
def dispatcher(
    sender: RecordingNotificationSender,
    renderer: NotificationRenderer,
) -> NotificationDispatcher:
    return NotificationDispatcher(sender, renderer)


@pytest.fixture()
def notify_order_placed(
    inbox: InMemoryInboxGateway,
    users: InMemoryUserQueryGateway,
    orders: StubOrderQueryGateway,
    dispatcher: NotificationDispatcher,
) -> NotifyOrderPlacedHandler:
    return NotifyOrderPlacedHandler(inbox, users, orders, dispatcher)


@pytest.fixture()
def notify_status_changed(
    inbox: InMemoryInboxGateway,
    users: InMemoryUserQueryGateway,
    dispatcher: NotificationDispatcher,
) -> NotifyOrderStatusChangedHandler:
    return NotifyOrderStatusChangedHandler(inbox, users, dispatcher)


@pytest.fixture()
def notify_address_changed(
    inbox: InMemoryInboxGateway,
    users: InMemoryUserQueryGateway,
    dispatcher: NotificationDispatcher,
) -> NotifyDeliveryAddressChangedHandler:
    return NotifyDeliveryAddressChangedHandler(inbox, users, dispatcher)


@pytest.fixture()
def seed_user(users: InMemoryUserQueryGateway) -> UserSeeder:
    """Puts one person into the read model and hands their view back."""

    def seed(
        user_id: str,
        role: UserRole = UserRole.CUSTOMER,
        external_id: str = CUSTOMER_ACCOUNT,
        *,
        locale: str = DEFAULT_LOCALE,
        notify_via: MessengerPlatform = MessengerPlatform.TELEGRAM,
        blocked: bool = False,
        linked: MessengerPlatform | None = None,
    ) -> UserView:
        attached = linked if linked is not None else notify_via
        view = UserView(
            id=UUID(user_id),
            phone_number="+79990000000",
            first_name="Иван",
            last_name=None,
            role=role.value,
            status=(UserStatus.BLOCKED if blocked else UserStatus.ACTIVE).value,
            block_reason="спам" if blocked else None,
            notify_via=notify_via.value,
            locale=locale,
            marketing_consent=False,
            accounts=(
                MessengerAccountView(
                    platform=attached.value,
                    external_id=external_id,
                    username=None,
                    linked_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        users.views[UserId(view.id)] = view
        return view

    return seed
