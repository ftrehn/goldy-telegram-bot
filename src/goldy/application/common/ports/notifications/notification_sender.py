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
    because the dispatcher picks a sender by it: a person whose notification
    target is MAX is written to by the MAX sender and by nothing else, so a
    Telegram id is never mistaken for an id that means something else there.

    ``send`` returns nothing and raises when the message did not arrive. Two
    kinds of failure, two errors. Somebody having blocked the bot is an answer
    the messenger will give again tomorrow, and it is reported as
    ``NotificationUndeliverableError`` so the dispatcher can count the person
    as skipped and go on to the next one. A timeout, a 5xx, a flood wait are
    worth another go and reach the caller as an ``InfrastructureError``,
    because raising all the way out is what puts the broker message back for
    redelivery.
    """

    @property
    @abstractmethod
    def platform(self) -> MessengerPlatform:
        """The messenger this sender can reach, and the only one."""
        raise NotImplementedError

    @abstractmethod
    async def send(self, notification: OutgoingNotification) -> None:
        """Writes the message to the account.

        Raises:
            NotificationUndeliverableError: the account cannot be written to,
                now or on any retry — the person blocked the bot, deleted the
                account, the chat is gone.
            InfrastructureError: the messenger could not be reached and a
                later attempt may well succeed.
        """
        raise NotImplementedError
