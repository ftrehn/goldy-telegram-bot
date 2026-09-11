"""Stand-ins for the two ports the notifier cannot exercise in a unit test.

The inbox is a table and the sender is the Bot API. Everything else in these
tests is the real thing — including the Fluent renderer, because "the message
rendered" is one of the decisions under test rather than scaffolding.
"""

from typing import Final, final, override
from uuid import UUID

from goldy.application.common.ports.notifications import (
    InboxGateway,
    NotificationSender,
    OutgoingNotification,
)
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@final
class InMemoryInboxGateway(InboxGateway):
    """Claims a message the first time it is seen and never again.

    The same answer the unique primary key gives: the first caller is told it
    wrote a row, everybody after it is told it did not.
    """

    def __init__(self) -> None:
        self.claimed: dict[UUID, str] = {}

    @override
    async def claim(self, message_id: UUID, event_type: str) -> bool:
        if message_id in self.claimed:
            return False

        self.claimed[message_id] = event_type
        return True


@final
class RecordingNotificationSender(NotificationSender):
    """Remembers what was sent, and can refuse or fail on demand.

    ``unreachable`` is somebody who blocked the bot — an ordinary answer, so
    ``send`` returns False. ``failure`` is the other kind: a timeout or a 5xx,
    which the real adapter turns into an exception precisely so the broker
    redelivers the message.
    """

    def __init__(
        self,
        platform: MessengerPlatform = MessengerPlatform.TELEGRAM,
    ) -> None:
        self.sent: list[OutgoingNotification] = []
        self.unreachable: set[str] = set()
        self.failure: Exception | None = None
        self._platform: Final[MessengerPlatform] = platform

    @property
    @override
    def platform(self) -> MessengerPlatform:
        return self._platform

    @override
    async def send(self, notification: OutgoingNotification) -> bool:
        if self.failure is not None:
            raise self.failure

        if notification.external_id in self.unreachable:
            return False

        self.sent.append(notification)
        return True

    def text_to(self, external_id: str) -> str:
        """What this account was told, as one string.

        Raises:
            AssertionError: nothing was sent to that account.
        """
        texts = [n.text for n in self.sent if n.external_id == external_id]

        if not texts:
            msg = f"Nothing was sent to {external_id!r}."
            raise AssertionError(msg)

        return "\n".join(texts)
