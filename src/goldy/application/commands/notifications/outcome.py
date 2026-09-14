from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class NotificationOutcome:
    """What one notification command did, for the worker log.

    ``skipped`` is not a failure. A person who blocked the bot, a manager whose
    notification target is a messenger this sender cannot reach, a customer
    whose account was unlinked — all of them are ordinary answers, and all of
    them still count, because a number that is always zero and suddenly is not
    is the only warning anybody gets.

    ``already_handled`` marks a redelivery the inbox refused. Seeing it now and
    then is the outbox working as designed; seeing it constantly means messages
    are being redelivered faster than they are being acknowledged.
    """

    delivered: int
    skipped: int
    already_handled: bool = False

    @classmethod
    def duplicate(cls) -> Self:
        """The message had been handled before, so nothing was sent."""
        return cls(delivered=0, skipped=0, already_handled=True)
