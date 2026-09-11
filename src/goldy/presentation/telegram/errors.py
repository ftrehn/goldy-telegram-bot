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


class DeepLinkPayloadTooLongError(TelegramPresentationError):
    """Raised when an identifier will not fit in the 64 characters ``/start`` has.

    Deliberately absent from ``ERROR_TEXTS``, unlike the three above. Those are
    raised while serving somebody's update and need words a customer can read;
    this one is raised while *building* a link, by an export or by a manager's
    tool, where the reader is us and the right outcome is a failure loud enough
    to stop the batch. A link built from a truncated identifier is not a
    shorter link, it is a link that opens the wrong product.
    """


class BotWithoutUsernameError(TelegramPresentationError):
    """Raised when Telegram reports this bot has no username to address.

    Cannot happen to a bot that BotFather created, and is still checked: the
    alternative is an ``https://t.me/None/?start=…`` printed onto a web page,
    where nothing fails until a customer clicks it.
    """
