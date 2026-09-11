"""Nothing but discipline keeps ``ERROR_TEXTS`` complete, so this does instead.

An error with no entry is logged at ``error`` and shown as "something went
wrong, we are looking into it". For a defect that is right; for an empty cart
or a mistyped address it is a lie that also buries the real failures in the
log. The next error class somebody writes would quietly join them.
"""

from types import ModuleType
from typing import Final

from goldy.application import error as application_errors
from goldy.application.error import (
    ApplicationError,
    CatalogSnapshotError,
    CatalogSourceError,
    DuplicateInboxMessageError,
    PaginationError,
)
from goldy.domain.carts import errors as cart_errors
from goldy.domain.catalog import errors as catalog_errors
from goldy.domain.common.error import AppError
from goldy.domain.common.values import errors as value_errors
from goldy.domain.common.values.errors import NonPositiveQuantityError
from goldy.domain.orders import errors as order_errors
from goldy.domain.orders.errors import TooLongDeliveryAddressError
from goldy.domain.users import errors as user_errors
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.handlers.errors import ERROR_TEXTS

ERROR_MODULES: Final[tuple[ModuleType, ...]] = (
    cart_errors,
    order_errors,
    catalog_errors,
    value_errors,
    user_errors,
    application_errors,
)

ANSWERED_ELSEWHERE: Final[frozenset[type[AppError]]] = frozenset(
    {
        ApplicationError,
        PaginationError,
        DuplicateInboxMessageError,
        CatalogSourceError,
        CatalogSnapshotError,
    },
)
"""The classes that deliberately have no message of their own.

``ApplicationError`` is the base: an entry for it would cover every subclass
written afterwards, which is exactly the silence this test exists to prevent.
``PaginationError`` and ``DuplicateInboxMessageError`` are ours to fix rather
than anybody's to act on — one is a bad call site, the other a redelivery the
worker swallows on purpose. The two catalog ones are raised inside the seeder
CLI, which has no chat to answer in and no i18n to answer with.
"""


def declared_errors() -> tuple[type[AppError], ...]:
    """Every error class those modules define, ignoring what they import."""
    return tuple(
        sorted(
            {
                value
                for module in ERROR_MODULES
                for value in vars(module).values()
                if isinstance(value, type)
                and issubclass(value, AppError)
                and value.__module__ == module.__name__
            },
            key=lambda error: error.__name__,
        ),
    )


def test_every_error_the_shop_can_raise_has_a_message() -> None:
    uncovered = [
        error.__name__
        for error in declared_errors()
        if error not in ANSWERED_ELSEWHERE and _message_for(error) is None
    ]

    assert uncovered == []


def test_the_field_error_tail_does_not_shadow_a_specific_message() -> None:
    """Because the lookup walks the MRO rather than reading the table in order.

    Worth pinning down: the quantity errors are ``DomainFieldError``
    descendants with a tail entry sitting over them, and an implementation that
    matched on anything but the nearest class would answer every one of them
    with "check what you entered".
    """
    assert _message_for(NonPositiveQuantityError) == text_keys.QUANTITY_TOO_SMALL


def test_the_tail_catches_a_field_error_nobody_listed() -> None:
    assert _message_for(TooLongDeliveryAddressError) == text_keys.ERROR_CHECK_VALUE


def _message_for(error: type[AppError]) -> str | None:
    return next(
        (ERROR_TEXTS[ancestor] for ancestor in error.__mro__ if ancestor in ERROR_TEXTS),
        None,
    )
