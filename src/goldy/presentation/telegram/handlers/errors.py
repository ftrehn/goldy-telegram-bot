import logging
from collections.abc import Mapping
from typing import Final

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent, Message
from aiogram_i18n import I18nContext

from goldy.application.error import UserAlreadyExistsError, UserNotFoundError
from goldy.domain.common.error import AppError
from goldy.domain.users.errors import (
    AuthorizationError,
    LastMessengerAccountError,
    NotificationTargetNotLinkedError,
    PlatformAlreadyLinkedError,
    UserIsBlockedError,
)
from goldy.presentation.telegram.errors import (
    ContactBelongsToSomeoneElseError,
    ContactHasNoPhoneNumberError,
    RegistrationRequiredError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

router: Final[Router] = Router(name="errors")

UNKNOWN_ERROR_KEY: Final[str] = "error-unknown"

ERROR_TEXTS: Final[Mapping[type[AppError], str]] = {
    AuthorizationError: "error-forbidden",
    UserIsBlockedError: "error-blocked",
    UserNotFoundError: "error-not-found",
    UserAlreadyExistsError: "error-already-exists",
    LastMessengerAccountError: "error-last-account",
    NotificationTargetNotLinkedError: "error-last-account",
    PlatformAlreadyLinkedError: "error-already-exists",
    RegistrationRequiredError: "auth-registration-required",
    ContactBelongsToSomeoneElseError: "auth-contact-not-yours",
    ContactHasNoPhoneNumberError: "auth-contact-without-number",
}
"""One table instead of try/except in every handler.

An error missing from here still reaches the person as something, and reaches
the log as everything — which is the right way round. Silence is the failure
mode worth designing against: an update that dies quietly looks to the user
like the bot ignoring them.
"""


def _text_key(exception: Exception) -> str | None:
    """Finds the message for this error, or for the closest base it has.

    Walking the MRO means a new subclass of an already-handled error is covered
    the day it is written, rather than falling through to the generic message.
    """
    for error_type in type(exception).__mro__:
        if error_type in ERROR_TEXTS:
            return ERROR_TEXTS[error_type]

    return None


def _message_of(event: ErrorEvent) -> Message | None:
    update = event.update
    if update.message is not None:
        return update.message
    if update.callback_query is not None:
        return update.callback_query.message  # type: ignore[return-value]
    return None


@router.errors(ExceptionTypeFilter(AppError))
async def handle_app_error(event: ErrorEvent, i18n: I18nContext | None = None) -> None:
    """Turns a raised domain rule into something a person can read.

    ``i18n`` is optional rather than required because the context is created by
    a middleware: an error thrown before that one ran — a database outage during
    authentication, say — would otherwise fail again here on a missing argument,
    and the original failure would never reach the log.
    """
    exception = event.exception
    key = _text_key(exception)

    if key is None:
        logger.error(
            "unhandled application error",
            exc_info=exception,
        )
        key = UNKNOWN_ERROR_KEY
    else:
        logger.info("refused: %s: %s", type(exception).__name__, exception)

    message = _message_of(event)

    if message is None or i18n is None:
        return

    await message.answer(i18n.get(key))
