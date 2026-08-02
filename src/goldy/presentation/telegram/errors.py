from goldy.domain.common.error import AppError


class TelegramPresentationError(AppError):
    """Base for everything that can go wrong between Telegram and a command."""


class RegistrationRequiredError(TelegramPresentationError):
    """Raised when an unregistered account tries to do anything but register."""


class ContactBelongsToSomeoneElseError(TelegramPresentationError):
    """Raised when the shared contact card is not the sender's own.

    Telegram lets a person forward any card from their address book, so the
    ``request_contact`` button is not by itself proof of ownership. Without this
    check somebody could register under a stranger's number and — because
    registration links accounts by number — walk straight into their account.
    """


class ContactHasNoPhoneNumberError(TelegramPresentationError):
    """Raised when a contact arrives with no number on it at all."""
