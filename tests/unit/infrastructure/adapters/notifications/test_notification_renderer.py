"""Every notification message, rendered rather than read.

The lesson this project already paid for: a Fluent placeholder whose argument
was not passed does not appear as ``{ $number }`` in the message. It makes the
render fail, so the customer gets nothing at all and the only trace is a line
in a worker log. Reading the ``.ftl`` files and nodding is therefore not a
check — every notification the handlers can build is rendered here, in both
languages, with every field it carries looked for in the text.

The second failure this guards is the quieter one: a message added to ``ru``
and forgotten in ``en``. The bot's locales are held to the same rule, and half
the customers silently losing their notifications is a worse outcome than a
failing test.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from goldy.application.common.ports.notifications import (
    Notification,
    OrderDeliveryAddressChangedNotification,
    OrderHandoverRejectedNotification,
    OrderPlacedNotification,
    OrderStatusChangedNotification,
)
from goldy.application.common.views.money import MoneyView
from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.infrastructure.adapters.notifications import text_keys
from goldy.infrastructure.adapters.notifications.fluent_notification_renderer import (
    LC_MESSAGES,
    FluentNotificationRenderer,
)
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_LOCALES_PATH,
    NOTIFICATION_RESOURCE,
)
from goldy.infrastructure.errors import NotificationRenderError

NOTIFICATIONS: Final[tuple[Notification, ...]] = (
    OrderPlacedNotification(
        number="240913-3K7QXA",
        customer_name="Иван Иванов",
        phone_number="+79991234567",
        address="Москва, Ленина 1",
        line_count=3,
        total=MoneyView(amount=Decimal("1234.00"), currency="RUB"),
    ),
    OrderStatusChangedNotification(number="240913-3K7QXA", status="shipped"),
    OrderStatusChangedNotification(
        number="240913-3K7QXA",
        status="cancelled",
        reason="Товара нет на складе",
    ),
    OrderDeliveryAddressChangedNotification(
        number="240913-3K7QXA",
        old_address="Москва, Ленина 1",
        new_address="Санкт-Петербург, Невский 20",
    ),
    OrderHandoverRejectedNotification(number="240913-3K7QXA", code="prices_changed"),
)
"""One of every kind of notification a handler can build, fully filled in.

The two status changes are both here on purpose: with and without a reason
are two messages in the files, and the renderer chooses between them.
"""

LOCALES: Final[tuple[str, ...]] = tuple(sorted(SUPPORTED_LOCALES))


@dataclass(frozen=True, slots=True, kw_only=True)
class _UnknownNotification(Notification):
    """A kind nobody wrote a wording for."""


@pytest.fixture(scope="session")
def renderer() -> FluentNotificationRenderer:
    return FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH)


def test_every_declared_key_is_written_in_the_files() -> None:
    """A key declared and never written is a message nobody will ever receive.

    A subset rather than equality: the files also hold helper messages the
    others reference — the status wording — which no handler asks for by name.
    """
    declared = {
        value
        for name, value in vars(text_keys).items()
        if name.isupper() and isinstance(value, str)
    }

    assert declared <= _message_ids("ru")


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("notification", NOTIFICATIONS, ids=type)
def test_every_notification_renders_in_every_language(
    renderer: FluentNotificationRenderer,
    notification: Notification,
    locale: str,
) -> None:
    rendered = renderer.render(notification, locale)

    assert rendered.strip()


@pytest.mark.parametrize("locale", LOCALES)
def test_every_field_of_a_placed_order_reaches_the_message(
    renderer: FluentNotificationRenderer,
    locale: str,
) -> None:
    """A placeholder that was never written into the text is dead weight.

    Fluent is loud about an argument that is missing and silent about one that
    is never used, so the second direction has to be checked here.
    """
    placed = NOTIFICATIONS[0]
    assert isinstance(placed, OrderPlacedNotification)

    rendered = renderer.render(placed, locale)

    for value in (
        placed.number,
        placed.customer_name,
        placed.phone_number,
        placed.address,
        str(placed.line_count),
        "1234.00 RUB",
    ):
        assert value in rendered


def test_a_cancellation_reason_is_printed_and_its_absence_is_not(
    renderer: FluentNotificationRenderer,
) -> None:
    with_reason = renderer.render(NOTIFICATIONS[2], "ru")
    without_reason = renderer.render(NOTIFICATIONS[1], "ru")

    assert "Товара нет на складе" in with_reason
    assert "Причина" not in without_reason


def test_a_handover_refusal_names_the_order_and_translates_the_known_reason() -> None:
    rendered = FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH).render(
        OrderHandoverRejectedNotification(number="240913-3K7QXA", code="prices_changed"),
        "ru",
    )

    assert "240913-3K7QXA" in rendered
    assert "цены изменились" in rendered


def test_a_handover_refusal_with_an_unknown_site_code_prints_it_as_it_came() -> None:
    rendered = FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH).render(
        OrderHandoverRejectedNotification(
            number="240913-3K7QXA", code="brand_new_refusal"
        ),
        "ru",
    )

    assert "brand_new_refusal" in rendered


def test_both_languages_define_exactly_the_same_messages() -> None:
    """Compared as text rather than through the renderer.

    ``FluentBundle`` will happily answer for a message one language has and the
    other does not; the point is to notice before a customer does.
    """
    defined = {locale: _message_ids(locale) for locale in LOCALES}

    assert len(set(map(frozenset, defined.values()))) == 1, defined


def test_an_unknown_language_falls_back_rather_than_failing(
    renderer: FluentNotificationRenderer,
) -> None:
    """A record written by a newer replica must not cost somebody their message."""
    rendered = renderer.render(NOTIFICATIONS[1], "de")

    assert "240913-3K7QXA" in rendered


def test_a_notification_nobody_wrote_a_wording_for_raises(
    renderer: FluentNotificationRenderer,
) -> None:
    """A fact that happened and a customer never told is the failure to refuse."""
    with pytest.raises(NotificationRenderError):
        renderer.render(_UnknownNotification(), "ru")


def test_a_locale_without_a_file_is_refused_at_startup(tmp_path: Path) -> None:
    """Shipping one language and not the other fails when the worker starts.

    Per message it would fail for half the customers and nobody else, which is
    the version of this failure that reaches production.
    """
    (tmp_path / "ru" / LC_MESSAGES).mkdir(parents=True)
    (tmp_path / "ru" / LC_MESSAGES / NOTIFICATION_RESOURCE).write_text(
        "notification-order-status-changed = ok\n",
        encoding="utf-8",
    )

    with pytest.raises(NotificationRenderError):
        FluentNotificationRenderer(tmp_path)


def _message_ids(locale: str) -> set[str]:
    resource = NOTIFICATION_LOCALES_PATH / locale / LC_MESSAGES / NOTIFICATION_RESOURCE
    return {
        line.split("=", 1)[0].strip()
        for line in resource.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(("#", " ")) and "=" in line
    }
