from goldy.domain.common.error import AppError


class ApplicationError(AppError):
    """Base exception class for the application layer."""


class PaginationError(ApplicationError):
    """Raised when pagination parameters are invalid."""


class DuplicateInboxMessageError(ApplicationError):
    """Raised when a message with the same message_id was already processed."""
