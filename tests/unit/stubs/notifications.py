"""Stand-ins for the ports the notifier cannot exercise in a unit test.

The inbox is a table, the sender is the Bot API and the mediator is a stack of
pipelines over a session. Everything else in these tests is the real thing —
including the Fluent renderer, because "the message rendered" is one of the
decisions under test rather than scaffolding.
"""

from typing import Final, cast, final, override
from uuid import UUID

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.notifications import (
    InboxGateway,
    NotificationSender,
    OutgoingNotification,
)
from goldy.application.error import NotificationUndeliverableError
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

    ``unreachable`` is somebody who blocked the bot — an answer the messenger
    gives again tomorrow, so ``send`` raises ``NotificationUndeliverableError``
    the way the real adapter does. ``failure`` is the other kind: a timeout or
    a 5xx, which the real adapter turns into an infrastructure error precisely
    so the broker redelivers the message.
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
    async def send(self, notification: OutgoingNotification) -> None:
        if self.failure is not None:
            raise self.failure

        if notification.external_id in self.unreachable:
            msg = f"Account {notification.external_id} cannot be written to."
            raise NotificationUndeliverableError(msg)

        self.sent.append(notification)

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


@final
class RecordingSender(Sender):
    """Keeps every request it was handed and answers with one delivery.

    What a subscriber test wants to know is which command was built out of a
    broker message, not what the handler behind it would have done.
    """

    def __init__(self) -> None:
        self.requests: list[BaseRequest[object]] = []

    @override
    async def send[TResponse](self, request: BaseRequest[TResponse]) -> TResponse:
        self.requests.append(request)
        return cast("TResponse", NotificationOutcome(delivered=1, skipped=0))
