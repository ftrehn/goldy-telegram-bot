"""Who a notification actually goes to, decided from the user's own settings.

One function, used by every notification handler, because "whom do we write to"
is the same question each time and answering it twice is how one notification
starts respecting a setting the other ignores.
"""

import logging
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform

logger: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NotificationRecipient:
    """One messenger account to write to, in one language."""

    user_id: UUID
    platform: MessengerPlatform
    external_id: str
    locale: str


def recipient_for(user: UserView) -> NotificationRecipient | None:
    """Where to write to this person, or nothing if we must not.

    Three ways it comes back empty, and none of them is an error.

    A blocked person is not written to at all. Blocking is how the shop stops
    dealing with somebody, and an order notification is still the shop talking
    to them.

    ``notify_via`` names a platform they no longer have linked. :class:`User`
    keeps the two in step, so this should not happen — but the view is read
    from the database rather than from the aggregate, and sending to an
    arbitrary account instead of the chosen one is worse than silence.

    ``notify_via`` holds a platform this build does not know. The column is
    plain text so that adding a messenger is a code change and not a
    migration, which also means a newer replica can have written a value this
    one cannot read.
    """
    if user.is_blocked:
        logger.debug("notifications: %s is blocked, not writing", user.id)
        return None

    platform = _platform_of(user.notify_via)

    if platform is None:
        logger.warning(
            "notifications: %s is set to be notified via unknown platform %r",
            user.id,
            user.notify_via,
        )
        return None

    account = next(
        (a for a in user.accounts if a.platform == user.notify_via),
        None,
    )

    if account is None:
        logger.warning(
            "notifications: %s has no %s account to be notified through",
            user.id,
            user.notify_via,
        )
        return None

    return NotificationRecipient(
        user_id=user.id,
        platform=platform,
        external_id=account.external_id,
        locale=user.locale,
    )


def _platform_of(value: str) -> MessengerPlatform | None:
    return next((p for p in MessengerPlatform if p.value == value), None)
