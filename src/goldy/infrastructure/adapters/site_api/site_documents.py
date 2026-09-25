"""Reading the site's JSON, and turning its refusals into the ports' errors.

The site's contract is ``docs/API.md`` in its repository. Money comes as a
string with two decimals, dates as ISO 8601 with an offset, absence as
``null``. Every helper here reads one of those strictly and raises
:class:`SiteApiResponseError` otherwise: a body that is not the contract is a
defect on one side or the other, and guessing at it would put a wrong number
in front of a customer.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, NoReturn

from goldy.application.error import (
    SiteCustomerNotLinkedError,
    SiteUnavailableError,
)
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.money import Money
from goldy.infrastructure.errors import (
    SiteApiError,
    SiteApiRejectedError,
    SiteApiResponseError,
    SiteApiUnavailableError,
)

CUSTOMER_NOT_LINKED: Final[str] = "customer_not_linked"


def as_object(value: object, what: str) -> Mapping[str, object]:
    """``value`` as a JSON object, or a contract error naming ``what``."""
    if not isinstance(value, dict):
        msg = f"The site sent {what} that is not an object."
        raise SiteApiResponseError(msg)
    return value


def as_list(value: object, what: str) -> list[object]:
    """``value`` as a JSON array, or a contract error naming ``what``."""
    if not isinstance(value, list):
        msg = f"The site sent {what} that is not a list."
        raise SiteApiResponseError(msg)
    return value


def text(document: Mapping[str, object], key: str) -> str:
    """A required, non-empty string field."""
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"The site sent no '{key}'."
        raise SiteApiResponseError(msg)
    return value.strip()


def optional_text(document: Mapping[str, object], key: str) -> str | None:
    """A string field that may be ``null`` or missing; blank reads as absent."""
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"The site sent '{key}' that is not text."
        raise SiteApiResponseError(msg)
    return value.strip() or None


def flag(document: Mapping[str, object], key: str) -> bool:
    """A boolean field; a missing one reads as false."""
    value = document.get(key, False)
    if not isinstance(value, bool):
        msg = f"The site sent '{key}' that is not true or false."
        raise SiteApiResponseError(msg)
    return value


def integer(document: Mapping[str, object], key: str) -> int:
    """A required whole-number field."""
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"The site sent '{key}' that is not a whole number."
        raise SiteApiResponseError(msg)
    return value


def optional_integer(document: Mapping[str, object], key: str) -> int | None:
    value = document.get(key)
    return None if value is None else integer(document, key)


def decimal(document: Mapping[str, object], key: str) -> Decimal | None:
    """An amount the site sends as a string, ``"1250.00"``; ``null`` is absent.

    A number rather than a string is refused: the site promises strings
    precisely so that kopecks survive, and a float here means someone broke
    that promise.
    """
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"The site sent '{key}' that is not an amount string."
        raise SiteApiResponseError(msg)
    try:
        amount = Decimal(value)
    except InvalidOperation as e:
        msg = f"The site sent '{key}' = {value!r}, which is not an amount."
        raise SiteApiResponseError(msg) from e
    if not amount.is_finite():
        msg = f"The site sent '{key}' = {value!r}, which is not an amount."
        raise SiteApiResponseError(msg)
    return amount


def currency(value: object) -> Currency:
    """The site's ``"RUB"`` as ours; anything we cannot price in is refused."""
    if not isinstance(value, str):
        msg = "The site sent a currency that is not text."
        raise SiteApiResponseError(msg)
    try:
        return Currency(value.strip().lower())
    except ValueError as e:
        msg = f"The site priced in {value!r}, which this shop does not handle."
        raise SiteApiResponseError(msg) from e


def money(
    document: Mapping[str, object], key: str, currency_code: object
) -> Money | None:
    """An amount and a currency as one value, or ``None`` when absent."""
    amount = decimal(document, key)
    if amount is None:
        return None
    return Money(amount.quantize(Decimal("0.01")), currency(currency_code))


def moment(document: Mapping[str, object], key: str) -> datetime | None:
    """An ISO 8601 moment with an offset; ``null`` is absent.

    A moment without an offset is refused: the order feed is asked "changed
    since" against these, and a naive time read in the wrong zone skips or
    repeats three hours of changes.
    """
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"The site sent '{key}' that is not a date."
        raise SiteApiResponseError(msg)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        msg = f"The site sent '{key}' = {value!r}, which is not a date."
        raise SiteApiResponseError(msg) from e
    if parsed.tzinfo is None:
        msg = f"The site sent '{key}' = {value!r} without an offset."
        raise SiteApiResponseError(msg)
    return parsed


def reraise_common(error: SiteApiError, where: str) -> NoReturn:
    """Turns what every endpoint shares into the port's errors, and re-raises.

    Callers first handle the codes their endpoint gives meaning to, then hand
    the rest here. An outage becomes :class:`SiteUnavailableError`; the site
    forgetting the subject becomes :class:`SiteCustomerNotLinkedError`;
    everything else — a bad token, a missing scope, a body that is not the
    contract — is a fault of configuration or of one side's code, and stays an
    infrastructure error for the log to show.

    Raises:
        SiteUnavailableError: the site did not answer.
        SiteCustomerNotLinkedError: the site does not know the subject.
        SiteApiError: anything else, unchanged.
    """
    if isinstance(error, SiteApiUnavailableError):
        msg = f"The site did not answer {where}: {error}"
        raise SiteUnavailableError(msg) from error

    if isinstance(error, SiteApiRejectedError) and error.code == CUSTOMER_NOT_LINKED:
        msg = f"The site no longer links this person ({where})."
        raise SiteCustomerNotLinkedError(msg) from error

    raise error
