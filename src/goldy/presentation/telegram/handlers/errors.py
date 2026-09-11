import logging
from collections.abc import Mapping
from typing import Final

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from aiogram_i18n import I18nContext

from goldy.application.error import (
    AuthenticationError,
    CartNotFoundError,
    CartRepricedError,
    OrderNotFoundError,
    PriceTypeNotConfiguredError,
    ProductNotFoundError,
    ProductNotPricedError,
    SearchTermError,
    UnsupportedPriceTypeError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from goldy.domain.carts.errors import (
    CartLineLimitExceededError,
    CartLineNotFoundError,
    EmptyCartError,
)
from goldy.domain.common.error import AppError, DomainFieldError
from goldy.domain.common.values.errors import (
    CurrencyMismatchError,
    NonPositiveQuantityError,
    QuantityLimitExceededError,
)
from goldy.domain.orders.errors import (
    CancellationReasonRequiredError,
    CustomerCannotCancelProcessedOrderError,
    EmptyOrderError,
    OrderNotEditableError,
    OrderStatusTransitionError,
    UnpricedCartLineError,
)
from goldy.domain.users.errors import (
    AuthorizationError,
    LastMessengerAccountError,
    MessengerAccountNotLinkedError,
    NotificationTargetNotLinkedError,
    PlatformAlreadyLinkedError,
    UserAlreadyBlockedError,
    UserIsBlockedError,
    UserNotBlockedError,
)
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.replying import answer_update
from goldy.presentation.telegram.errors import (
    ContactBelongsToSomeoneElseError,
    ContactHasNoPhoneNumberError,
    RegistrationRequiredError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

router: Final[Router] = Router(name="errors")

ERROR_TEXTS: Final[Mapping[type[AppError], str]] = {
    AuthorizationError: text_keys.ERROR_FORBIDDEN,
    UserIsBlockedError: text_keys.ERROR_BLOCKED,
    UserNotFoundError: text_keys.ERROR_NOT_FOUND,
    UserAlreadyExistsError: text_keys.ERROR_ALREADY_EXISTS,
    LastMessengerAccountError: text_keys.ERROR_LAST_ACCOUNT,
    NotificationTargetNotLinkedError: text_keys.ERROR_LAST_ACCOUNT,
    PlatformAlreadyLinkedError: text_keys.ERROR_ALREADY_EXISTS,
    MessengerAccountNotLinkedError: text_keys.ERROR_ACCOUNT_NOT_LINKED,
    UserAlreadyBlockedError: text_keys.ERROR_ALREADY_BLOCKED,
    UserNotBlockedError: text_keys.ERROR_NOT_BLOCKED,
    RegistrationRequiredError: text_keys.AUTH_REGISTRATION_REQUIRED,
    ContactBelongsToSomeoneElseError: text_keys.AUTH_CONTACT_NOT_YOURS,
    ContactHasNoPhoneNumberError: text_keys.AUTH_CONTACT_WITHOUT_NUMBER,
    AuthenticationError: text_keys.AUTH_REGISTRATION_REQUIRED,
    # The cart.
    EmptyCartError: text_keys.CART_EMPTY,
    CartLineNotFoundError: text_keys.CART_LINE_NOT_FOUND,
    CartLineLimitExceededError: text_keys.CART_FULL,
    CartNotFoundError: text_keys.CART_NOT_FOUND,
    CartRepricedError: text_keys.CART_REPRICED,
    UnpricedCartLineError: text_keys.CART_LINE_UNAVAILABLE,
    ProductNotPricedError: text_keys.CART_LINE_UNAVAILABLE,
    # Quantities and money.
    NonPositiveQuantityError: text_keys.QUANTITY_TOO_SMALL,
    QuantityLimitExceededError: text_keys.QUANTITY_TOO_LARGE,
    CurrencyMismatchError: text_keys.MONEY_CURRENCY_MISMATCH,
    # Orders.
    EmptyOrderError: text_keys.ORDER_EMPTY,
    OrderStatusTransitionError: text_keys.ORDER_TRANSITION_REFUSED,
    CustomerCannotCancelProcessedOrderError: text_keys.ORDER_CANNOT_CANCEL,
    CancellationReasonRequiredError: text_keys.ORDER_REASON_REQUIRED,
    OrderNotEditableError: text_keys.ORDER_NOT_EDITABLE,
    OrderNotFoundError: text_keys.ORDER_NOT_FOUND,
    # The catalog and the search over it.
    ProductNotFoundError: text_keys.CATALOG_PRODUCT_GONE,
    PriceTypeNotConfiguredError: text_keys.CATALOG_PRICE_MISSING,
    UnsupportedPriceTypeError: text_keys.CATALOG_PRICE_UNSUPPORTED,
    SearchTermError: text_keys.SEARCH_TERM_TOO_SHORT,
    # Last on purpose: see below.
    DomainFieldError: text_keys.ERROR_CHECK_VALUE,
}
"""One table instead of try/except in every handler.

An error missing from here still reaches the person as something, and reaches
the log as everything — which is the right way round. Silence is the failure
mode worth designing against: an update that dies quietly looks to the user
like the bot ignoring them.

Every refusal the buying flow can produce has an entry, and that is not
thoroughness for its own sake. A miss is logged at ``error`` and rendered as
"something went wrong, we are looking into it" — so a table with only the user
errors in it would report an empty cart, a quantity of zero and a mistyped
address as outages, and the most common path through the shop would read like
the bot is broken.

``DomainFieldError`` is the tail, and it is written last only for a reader: the
lookup walks the exception's MRO and stops at the nearest match, so ordering
here changes nothing and a specific error keeps winning. What the tail buys is
that every field validation in the project — the address, the comment, the
cancellation reason, a name, a phone number — asks the person to check what
they typed instead of apologising for a defect that is not there.

``AuthenticationError`` maps to the registration prompt rather than to a
refusal. It means only that the account writing to us belongs to nobody, and
the honest answer to that is the same invitation ``/start`` gives.
"""


@router.errors(ExceptionTypeFilter(AppError))
async def handle_app_error(event: ErrorEvent, i18n: I18nContext) -> None:
    """Turns a raised domain rule into something a person can read.

    ``i18n`` is required, not optional. Everything reaching here was raised by
    a handler, and by then the i18n middleware has run — the one earlier stage
    that could fail before it, the auth gate, answers its own failures because
    it is the last place that still can.

    The message is chosen by walking the exception's MRO, which is ordered
    nearest-first, so the first hit is the most specific. Matching that way
    rather than on the exact type means a new subclass of an already-handled
    error is covered the day it is written, instead of quietly falling through
    to the generic message.
    """
    exception = event.exception

    key = next(
        (
            ERROR_TEXTS[error_type]
            for error_type in type(exception).__mro__
            if error_type in ERROR_TEXTS
        ),
        None,
    )

    if key is None:
        logger.error("unhandled application error", exc_info=exception)
        key = text_keys.ERROR_UNKNOWN
    else:
        logger.info("refused: %s: %s", type(exception).__name__, exception)

    await answer_update(event.update, i18n.get(key))
