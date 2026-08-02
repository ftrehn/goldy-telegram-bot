import logging
from collections.abc import Mapping
from typing import Final

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
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
    RegistrationRequiredError: text_keys.AUTH_REGISTRATION_REQUIRED,
    ContactBelongsToSomeoneElseError: text_keys.AUTH_CONTACT_NOT_YOURS,
    ContactHasNoPhoneNumberError: text_keys.AUTH_CONTACT_WITHOUT_NUMBER,
}
"""One table instead of try/except in every handler.

An error missing from here still reaches the person as something, and reaches
the log as everything — which is the right way round. Silence is the failure
mode worth designing against: an update that dies quietly looks to the user
like the bot ignoring them.
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
