import logging
from dataclasses import dataclass
from typing import Final, final
from uuid import UUID

from goldy.application.common.views.user import UserView
from goldy.application.error import NotificationChannelUnavailableError
from goldy.domain.users.values.messenger_platform import MessengerPlatform

logger: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NotificationRecipient:
    """One messenger account to write to, in one language."""

    user_id: UUID
    platform: MessengerPlatform
    external_id: str
    locale: str


@final
class NotificationRecipientResolver:
    """Decides where a notification to a person actually goes, from their settings.

    An application service rather than a function, so it is injected into the
    dispatcher like every other collaborator and replaced in a test the same
    way. "Whom do we write to" is one question asked by every notification
    handler, and answering it in one object is how one notification cannot
    start respecting a setting another ignores.

    Two ways ``resolve`` comes back empty, and neither is an error.

    A blocked person is not written to at all. Blocking is how the shop stops
    dealing with somebody, and an order notification is still the shop talking
    to them.

    ``notify_via`` names a platform they no longer have linked. :class:`User`
    keeps the two in step, so this should not happen — but the view is read
    from the database rather than from the aggregate, and sending to an
    arbitrary account instead of the chosen one is worse than silence.

    A third case is an error. ``notify_via`` is stored as text so that adding
    a messenger is a code change and not a migration, which also means a newer
    replica can have written a platform this build cannot read. That is not a
    person's setting to skip quietly; it is this worker being behind the one
    that wrote the row, and the message waits on the broker until it catches
    up.
    """

    def resolve(self, user: UserView) -> NotificationRecipient | None:
        """Where to write to this person, or nothing if we must not.

        Raises:
            NotificationChannelUnavailableError: their notification target
                names a platform this build does not know.
        """
        if user.is_blocked:
            logger.debug("notifications: %s is blocked, not writing", user.id)
            return None

        platform = next(
            (member for member in MessengerPlatform if member.value == user.notify_via),
            None,
        )

        if platform is None:
            msg = (
                f"User '{user.id}' is set to be notified via {user.notify_via!r}, "
                f"which this build does not know."
            )
            raise NotificationChannelUnavailableError(msg)

        account = next(
            (account for account in user.accounts if account.platform == platform.value),
            None,
        )

        if account is None:
            logger.warning(
                "notifications: %s has no %s account to be notified through",
                user.id,
                platform.value,
            )
            return None

        return NotificationRecipient(
            user_id=user.id,
            platform=platform,
            external_id=account.external_id,
            locale=user.locale,
        )
