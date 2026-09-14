from collections.abc import Iterable, Mapping
from typing import Final, final

from goldy.application.common.ports.notifications import NotificationSender
from goldy.application.error import NotificationChannelUnavailableError
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@final
class NotificationSenders:
    """The senders this process holds, one per messenger it can write to.

    The dispatcher asks it for the sender behind a recipient's platform, and
    what it gets back is exactly one sender or an error — never a silent
    skip. Somebody who chose MAX as their notification target linked a MAX
    account first, which means a MAX process exists, which means the worker
    beside it is expected to hold a MAX sender. A worker that does not is a
    deployment that lets people choose a messenger nobody can write to, and
    that is reported rather than absorbed: the message stays on the broker
    until the sender is deployed, and the log says why.

    Today there is one sender and one platform. The registry exists so that
    the day a second one is added, the dispatcher does not change.
    """

    def __init__(self, senders: Iterable[NotificationSender]) -> None:
        self._by_platform: Final[Mapping[MessengerPlatform, NotificationSender]] = {
            sender.platform: sender for sender in senders
        }

    def for_platform(self, platform: MessengerPlatform) -> NotificationSender:
        """The sender that speaks this messenger.

        Raises:
            NotificationChannelUnavailableError: this process holds no sender
                for the platform.
        """
        sender = self._by_platform.get(platform)

        if sender is None:
            msg = f"No notification sender is configured for {platform.value}."
            raise NotificationChannelUnavailableError(msg)

        return sender
