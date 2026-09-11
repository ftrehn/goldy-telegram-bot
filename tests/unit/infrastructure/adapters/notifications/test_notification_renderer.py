"""Every notification message, rendered rather than read.

The lesson this project already paid for: a Fluent placeholder whose argument
was not passed does not appear as ``{ $number }`` in the message. It makes the
render fail, so the customer gets nothing at all and the only trace is a line
in a worker log. Reading the ``.ftl`` files and nodding is therefore not a
check — every key here is rendered with exactly the arguments its handler
builds, in both languages.

The second failure this guards is the quieter one: a message added to ``ru``
and forgotten in ``en``. The bot's locales are held to the same rule, and half
the customers silently losing their notifications is a worse outcome than a
failing test.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from goldy.application.commands.notifications import text_keys
from goldy.application.common.ports.notifications import NotificationText
from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.infrastructure.adapters.notifications.fluent_notification_renderer import (
    LC_MESSAGES,
    FluentNotificationRenderer,
)
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_LOCALES_PATH,
    NOTIFICATION_RESOURCE,
)
from goldy.infrastructure.errors import NotificationRenderError

MESSAGE_ARGUMENTS: Final[Mapping[str, Mapping[str, str | int]]] = {
    text_keys.NOTIFICATION_ORDER_PLACED: {
        "number": "1042",
        "customer": "Иван Иванов",
        "phone": "+79991234567",
        "address": "Москва, Ленина 1",
        "lines": 3,
        "total": "1234.00 RUB",
    },
    text_keys.NOTIFICATION_ORDER_STATUS_CHANGED: {
        "number": "1042",
        "status": "shipped",
    },
    text_keys.NOTIFICATION_ORDER_STATUS_CHANGED_REASON: {
        "number": "1042",
        "status": "cancelled",
        "reason": "Товара нет на складе",
    },
    text_keys.NOTIFICATION_ORDER_ADDRESS_CHANGED: {
        "number": "1042",
        "old_address": "Москва, Ленина 1",
        "new_address": "Санкт-Петербург, Невский 20",
    },
}
"""The arguments each handler actually passes, restated once.

Restated rather than imported, deliberately. A test that built the arguments by
calling the handler would pass whatever the handler happened to send, including
nothing; this table is the contract the ``.ftl`` files are held to.
"""

LOCALES: Final[tuple[str, ...]] = tuple(sorted(SUPPORTED_LOCALES))


@pytest.fixture(scope="session")
def renderer() -> FluentNotificationRenderer:
    return FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH)


def test_the_registry_covers_every_message_the_handlers_send() -> None:
    """The table above and the key registry are the same set.

    Adding a key and forgetting to render it here would leave exactly the kind
    of message this module exists to catch untested.
    """
    declared = {
        value
        for name, value in vars(text_keys).items()
        if name.isupper() and isinstance(value, str)
    }

    assert declared == set(MESSAGE_ARGUMENTS)


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("key", sorted(MESSAGE_ARGUMENTS))
def test_every_message_renders_in_every_language(
    renderer: FluentNotificationRenderer,
    key: str,
    locale: str,
) -> None:
    rendered = renderer.render(
        NotificationText(key=key, args=MESSAGE_ARGUMENTS[key]), locale
    )

    assert rendered.strip()


@pytest.mark.parametrize("locale", LOCALES)
def test_every_argument_reaches_the_message(
    renderer: FluentNotificationRenderer,
    locale: str,
) -> None:
    """A placeholder that was never written into the text is dead weight.

    Fluent is loud about an argument that is missing and silent about one that
    is never used, so the second direction has to be checked here.
    """
    key = text_keys.NOTIFICATION_ORDER_PLACED
    rendered = renderer.render(
        NotificationText(key=key, args=MESSAGE_ARGUMENTS[key]),
        locale,
    )

    for value in MESSAGE_ARGUMENTS[key].values():
        assert str(value) in rendered


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
    key = text_keys.NOTIFICATION_ORDER_STATUS_CHANGED

    rendered = renderer.render(
        NotificationText(key=key, args=MESSAGE_ARGUMENTS[key]),
        "de",
    )

    assert "1042" in rendered


def test_a_forgotten_argument_raises_instead_of_printing_itself(
    renderer: FluentNotificationRenderer,
) -> None:
    """The finding this whole module is built around, pinned down.

    ``{ $status }`` with no ``status`` passed does not render as text — Fluent
    reports an error and the renderer turns it into a refusal, which is why
    every message above is rendered rather than eyeballed.
    """
    with pytest.raises(NotificationRenderError):
        renderer.render(
            NotificationText(
                key=text_keys.NOTIFICATION_ORDER_STATUS_CHANGED,
                args={"number": "1042"},
            ),
            "ru",
        )


def test_a_message_nobody_wrote_raises(renderer: FluentNotificationRenderer) -> None:
    with pytest.raises(NotificationRenderError):
        renderer.render(NotificationText(key="notification-nothing"), "ru")


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
        if "=" in line and not line.startswith((" ", "#", "*", "["))
    }
