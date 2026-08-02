from dataclasses import dataclass, replace
from typing import Self, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.values.locale import Locale
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True)
class UserPreferences(ValueObject):
    """How the person wants to be reached, and in what language.

    Not ``kw_only``: mapped as a SQLAlchemy ``composite``, which rebuilds it
    positionally from its columns, so field order is part of the mapping.

    ``notify_via`` earns its place the moment someone links a second platform:
    without it an order-status message has no single obvious destination, and
    sending to every linked account is a good way to look broken.

    Whether the chosen platform is actually linked is not decided here — a
    value object cannot see the account list. :class:`User` enforces it.

    The ``with_*`` methods exist so a caller can change one setting without
    restating the others: building a fresh ``UserPreferences`` in a handler is
    how the language quietly resets every time somebody edits their
    notification channel.
    """

    notify_via: MessengerPlatform
    locale: Locale
    marketing_consent: bool = False

    def with_notify_via(self, platform: MessengerPlatform) -> Self:
        return replace(self, notify_via=platform)

    def with_locale(self, locale: Locale) -> Self:
        return replace(self, locale=locale)

    def with_marketing_consent(self, *, consent: bool) -> Self:
        return replace(self, marketing_consent=consent)

    @override
    def _validate(self) -> None:
        """Every field is already constrained by its own type."""
