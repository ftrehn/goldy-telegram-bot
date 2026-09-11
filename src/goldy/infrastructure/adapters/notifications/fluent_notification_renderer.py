import logging
from pathlib import Path
from typing import Final, final, override

from fluent.runtime import FluentBundle, FluentResource

from goldy.application.common.ports.notifications import (
    NotificationRenderer,
    NotificationText,
)
from goldy.domain.users.values.locale import DEFAULT_LOCALE, SUPPORTED_LOCALES
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_RESOURCE,
)
from goldy.infrastructure.errors import NotificationRenderError

logger: Final[logging.Logger] = logging.getLogger(__name__)

LC_MESSAGES: Final[str] = "LC_MESSAGES"


@final
class FluentNotificationRenderer(NotificationRenderer):
    """Words a notification from the ``.ftl`` files shipped beside it.

    ``fluent.runtime`` directly rather than the core the bot uses. That one is
    an aiogram component built around an update being handled, and there is no
    update here; going a layer lower also hands back the list of errors Fluent
    collected, which is what makes a forgotten argument fail loudly instead of
    printing ``{ $number }`` at a customer.

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
    def render(self, text: NotificationText, locale: str) -> str:
        """The message in the reader's language, or the default one.

        An unknown locale falls back rather than failing: the column is
        constrained to what we translate, but a record written by a newer
        replica can name a language this one does not ship, and a customer
        reading Russian instead of nothing is the better failure.

        Raises:
            NotificationRenderError: no such message, or an argument the
                message needs was not passed.
        """
        bundle = self._bundles.get(locale)

        if bundle is None:
            logger.warning(
                "notifications: no bundle for locale %r, falling back to %r",
                locale,
                self._default_locale,
            )
            bundle = self._bundles[self._default_locale]

        try:
            message = bundle.get_message(text.key)
        except LookupError as exc:
            msg = f"No notification message {text.key!r} in locale {locale!r}."
            raise NotificationRenderError(msg) from exc

        if message.value is None:
            msg = f"Notification message {text.key!r} has no value to render."
            raise NotificationRenderError(msg)

        rendered, errors = bundle.format_pattern(message.value, dict(text.args))

        if errors:
            reasons = "; ".join(str(error) for error in errors)
            msg = f"Could not render {text.key!r} in locale {locale!r}: {reasons}"
            raise NotificationRenderError(msg)

        return str(rendered)


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
