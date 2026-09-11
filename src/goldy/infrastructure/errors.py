from goldy.application.error import CatalogSourceError
from goldy.domain.common.error import AppError


class InfrastructureError(AppError):
    """Base exception class for the infrastructure layer."""


class UnregisteredTaskError(InfrastructureError):
    """Raised when scheduling a task whose name the broker does not know."""


class OutboxPublishError(InfrastructureError):
    """Raised when an outbox message could not be handed to its transport."""


class NotificationSendError(InfrastructureError):
    """Raised when a notification could not be delivered and is worth retrying.

    Narrower than "the send failed". Somebody having blocked the bot is an
    ordinary answer from Telegram and is reported by the sender returning
    False; this is for the answers that mean try again — a timeout, a flood
    wait, a 5xx — because raising is what puts the broker message back for
    redelivery.
    """


class NotificationRenderError(InfrastructureError):
    """Raised when a notification could not be worded at all.

    A missing translation or a placeholder whose argument was not passed.
    Loud on purpose: Fluent does not degrade a missing argument into visible
    text, so the alternative to raising is a message that never gets sent and
    never gets explained.
    """


class RepoError(InfrastructureError):
    """Raised when a persistence gateway fails to execute a statement."""


class HandlerNotFoundError(InfrastructureError):
    """Raised when a request reaches the mediator with no handler registered."""


class CatalogSourceReadError(InfrastructureError, CatalogSourceError):
    """Raised when a catalog snapshot cannot be read or understood.

    Both parents on purpose, and neither of them is decorative. It is an
    infrastructure error because a missing file and malformed JSON are failures
    of an adapter, and every library exception it meets — ``OSError``,
    ``UnicodeDecodeError``, ``JSONDecodeError`` — is turned into this one so
    that none of them escapes. It is a ``CatalogSourceError`` because that is
    what ``CatalogSource`` promises its callers, and a seeder catching the
    documented error has to catch this.
    """
