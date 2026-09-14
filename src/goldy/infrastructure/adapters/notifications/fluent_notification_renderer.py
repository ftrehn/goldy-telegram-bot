import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Final, final, override

from fluent.runtime import FluentBundle, FluentResource

from goldy.application.common.ports.notifications import (
    Notification,
    NotificationRenderer,
    OrderDeliveryAddressChangedNotification,
    OrderPlacedNotification,
    OrderStatusChangedNotification,
)
from goldy.domain.users.values.locale import DEFAULT_LOCALE, SUPPORTED_LOCALES
from goldy.infrastructure.adapters.notifications import text_keys
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_RESOURCE,
)
from goldy.infrastructure.errors import NotificationRenderError

logger: Final[logging.Logger] = logging.getLogger(__name__)

LC_MESSAGES: Final[str] = "LC_MESSAGES"

type FluentArguments = Mapping[str, str | int]


@final
class FluentNotificationRenderer(NotificationRenderer):
    """Words a notification from the ``.ftl`` files shipped beside it.

    ``fluent.runtime`` directly rather than the core the bot uses. That one is
    an aiogram component built around an update being handled, and there is no
    update here; going a layer lower also hands back the list of errors Fluent
    collected, which is what makes a forgotten argument fail loudly instead of
    printing ``{ $number }`` at a customer.

    The step from a typed notification to a key and its arguments happens
    here, in :meth:`_wording`, because it is knowledge of the translation
    files: which message spells a status change with a reason, that Fluent
    must be handed money already formatted or it prints the number by its own
    rules. The handler above never sees a key.

    Every language is parsed once, when the worker starts. A translation file
    that does not parse then takes the process down at startup, which is the
    only moment anybody is watching — the alternative is the first status
    change of the day failing for a reason nobody connects to a deployment.

    ``use_isolating`` is off. Fluent otherwise wraps every substituted value in
    directional isolation marks, which are invisible, count towards Telegram's
    message limit and turn an exact-text assertion into a puzzle.
    """

    def __init__(
        self,
        locales_path: Path,
        default_locale: str = DEFAULT_LOCALE,
    ) -> None:
        self._bundles: Final[dict[str, FluentBundle]] = _load_bundles(locales_path)
        self._default_locale: Final[str] = default_locale

    @override
    def render(self, notification: Notification, locale: str) -> str:
        """The message in the reader's language, or the default one.

        An unknown locale falls back rather than failing: the column is
        constrained to what we translate, but a record written by a newer
        replica can name a language this one does not ship, and a customer
        reading Russian instead of nothing is the better failure.

        Raises:
            NotificationRenderError: a notification this adapter has no wording
                for, no such message in the files, or a placeholder whose
                argument the notification does not carry.
        """
        bundle = self._bundles.get(locale)

        if bundle is None:
            logger.warning(
                "notifications: no bundle for locale %r, falling back to %r",
                locale,
                self._default_locale,
            )
            bundle = self._bundles[self._default_locale]

        key, arguments = _wording(notification)

        try:
            message = bundle.get_message(key)
        except LookupError as exc:
            msg = f"No notification message {key!r} in locale {locale!r}."
            raise NotificationRenderError(msg) from exc

        if message.value is None:
            msg = f"Notification message {key!r} has no value to render."
            raise NotificationRenderError(msg)

        rendered, errors = bundle.format_pattern(message.value, dict(arguments))

        if errors:
            reasons = "; ".join(str(error) for error in errors)
            msg = f"Could not render {key!r} in locale {locale!r}: {reasons}"
            raise NotificationRenderError(msg)

        return str(rendered)


def _wording(notification: Notification) -> tuple[str, FluentArguments]:
    """The Fluent message that spells this notification, and its arguments.

    Money is formatted here and not by Fluent: the currency arrives as data,
    and a Fluent function may only take literal arguments — the same
    restriction the bot's own price formatter works around.

    Raises:
        NotificationRenderError: a kind of notification nobody wrote a
            wording for. Loud, because the alternative is a fact that
            happened and a customer who was never told.
    """
    match notification:
        case OrderPlacedNotification():
            return text_keys.NOTIFICATION_ORDER_PLACED, {
                "number": notification.number,
                "customer": notification.customer_name,
                "phone": notification.phone_number,
                "address": notification.address,
                "lines": notification.line_count,
                "total": (
                    f"{notification.total.amount:.2f} {notification.total.currency}"
                ),
            }
        case OrderStatusChangedNotification(reason=None):
            return text_keys.NOTIFICATION_ORDER_STATUS_CHANGED, {
                "number": notification.number,
                "status": notification.status,
            }
        case OrderStatusChangedNotification(reason=str(reason)):
            return text_keys.NOTIFICATION_ORDER_STATUS_CHANGED_REASON, {
                "number": notification.number,
                "status": notification.status,
                "reason": reason,
            }
        case OrderDeliveryAddressChangedNotification():
            return text_keys.NOTIFICATION_ORDER_ADDRESS_CHANGED, {
                "number": notification.number,
                "old_address": notification.old_address,
                "new_address": notification.new_address,
            }
        case _:
            msg = f"No wording for {type(notification).__name__}."
            raise NotificationRenderError(msg)


def _load_bundles(locales_path: Path) -> dict[str, FluentBundle]:
    """One parsed bundle per language we ship.

    Raises:
        NotificationRenderError: a language has no notification file. Shipping
            one locale and not the other is how half the customers stop being
            written to, so it is refused at startup rather than per message.
    """
    bundles: dict[str, FluentBundle] = {}

    for locale in sorted(SUPPORTED_LOCALES):
        resource = locales_path / locale / LC_MESSAGES / NOTIFICATION_RESOURCE

        if not resource.is_file():
            msg = f"Notification translations for {locale!r} are missing: {resource}"
            raise NotificationRenderError(msg)

        bundle = FluentBundle([locale], use_isolating=False)
        bundle.add_resource(FluentResource(resource.read_text(encoding="utf-8")))
        bundles[locale] = bundle

    logger.debug("notifications: loaded locales %s", sorted(bundles))
    return bundles
