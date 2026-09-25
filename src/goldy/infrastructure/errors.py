from collections.abc import Mapping

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


class CatalogSourceUnavailableError(InfrastructureError, CatalogSourceError):
    """Raised when a catalog source could not be reached right now.

    The sibling of :class:`CatalogSourceReadError`, split by what the next
    attempt is likely to bring. A read error is an answer — a document that is
    not a catalog, a token the site refuses — and repeating the request gets
    the same answer. This one is the absence of an answer: a timeout, a refused
    connection, a 5xx, a 429. The scheduled sync is retried either way, but the
    log line has to tell the person on call which of the two they are looking
    at, and so does the type.
    """


class SiteApiError(InfrastructureError):
    """Raised when a call to the site API did not produce a usable answer.

    The client is shared by every conversation the bot has with the site —
    the catalog today, orders and linking later — so its errors say what went
    wrong with the HTTP exchange and nothing about what the caller wanted. The
    adapter built on top of it wraps them once more into the error its own
    port promises, which is how a caller catching ``CatalogSourceError`` never
    has to learn this class exists.

    Attributes:
        status: The HTTP status, or ``None`` when no response arrived.
        code: The site's stable error code from the envelope, when there was
            one. The site's message is free text and changes between versions;
            the code does not, and it is what a caller branches on.
        request_id: The ``X-Request-Id`` the request went out with, so the
            same call can be found in the site's log.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status: int | None = status
        self.code: str | None = code
        self.request_id: str | None = request_id


class SiteApiUnavailableError(SiteApiError):
    """Raised when the site did not answer, or answered "not now".

    A transport failure, a timeout, a 5xx or a 429 — everything a later
    attempt may well get past. ``retry_after`` carries the site's own
    ``Retry-After`` in seconds when it sent one.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status=status, code=code, request_id=request_id)
        self.retry_after: float | None = retry_after


class SiteApiRejectedError(SiteApiError):
    """Raised when the site refused the request itself — any other 4xx.

    A token the site does not know, a scope the client lacks, a malformed
    request. Repeating it gets the same refusal, so a caller retrying this is
    only filling the site's log.

    Attributes:
        details: ``error.details`` of the envelope — which positions changed
            price, why finance is refused — or an empty mapping when the site
            sent none. Read by the adapter that knows the endpoint; this
            class does not interpret it.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message, status=status, code=code, request_id=request_id)
        self.details: Mapping[str, object] = details or {}


class SiteApiResponseError(SiteApiError):
    """Raised when the site answered 2xx with something that is not the contract.

    A body that is not JSON, an envelope without ``data``, a cursor that is not
    a string. A defect on one of the two sides, never a transient condition.
    """
