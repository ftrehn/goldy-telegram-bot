from goldy.domain.common.error import AppError


class ApplicationError(AppError):
    """Base exception class for the application layer."""


class PaginationError(ApplicationError):
    """Raised when pagination parameters are invalid."""


class DuplicateInboxMessageError(ApplicationError):
    """Raised when a message with the same message_id was already processed."""


class AuthenticationError(ApplicationError):
    """Raised when the messenger account writing to us belongs to no user."""


class UserNotFoundError(ApplicationError):
    """Raised when a command names a user that does not exist."""


class UserAlreadyExistsError(ApplicationError):
    """Raised when a phone number or messenger account is already taken.

    Comes from the unique indexes rather than from a prior read: two
    simultaneous registrations both find nothing and both insert, so the
    conflict can only surface at write time.
    """
