from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class OutgoingNotification:
    """One rendered message, addressed to one messenger account.

    ``external_id`` is the account id the platform itself gave out, not a user
    id: the notifier writes to an account, and which account is the decision
    ``UserPreferences.notify_via`` already made.

    The text arrives rendered. Nothing below this line knows about locales or
    message keys, which is what lets the same port serve MAX later without the
    translations moving anywhere.
    """

    external_id: str
    text: str


class NotificationSender(Protocol):
    """Delivers a rendered notification through one messenger.

    :attr:`platform` is part of the port rather than a fact about the adapter,
    because the caller has to know: a person whose notification target is MAX
    must be skipped by a Telegram sender rather than written to at an id that
    means something else there.

    ``send`` answers whether the message arrived instead of raising when it did
    not. Somebody blocking the bot is an ordinary answer from Telegram and not
    an incident — it must not abort a batch, and it must not make the broker
    redeliver the message so the remaining recipients are written to twice.
    Failures that *are* worth retrying — a timeout, a 5xx, a flood wait — stay
    exceptions and reach the caller as an ``InfrastructureError``.
    """

    @property
    @abstractmethod
    def platform(self) -> MessengerPlatform:
        """The messenger this sender can reach, and the only one."""
        raise NotImplementedError

    @abstractmethod
    async def send(self, notification: OutgoingNotification) -> bool:
        """True when delivered, False when the account cannot be reached."""
        raise NotImplementedError
