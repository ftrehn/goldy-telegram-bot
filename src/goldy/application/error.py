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


class PriceTypeNotConfiguredError(ApplicationError):
    """Raised when no price type can be resolved for a customer at all.

    Not a missing binding — a customer without one falls back to the price type
    configured for the bot. This means the projection holds neither, which is a
    broken snapshot: the import finished with no price list in it, and the
    customer is the one who found out.
    """


class UnsupportedPriceTypeError(ApplicationError):
    """Raised when the customer's price type is denominated in an unknown currency.

    Deliberately an error and not a silent fall back to the default price list.
    Falling back would show somebody with a foreign-currency price list
    somebody else's prices without ever telling them.
    """


class ProductNotFoundError(ApplicationError):
    """Raised when a command or query names a product the catalog does not hold."""


class ProductNotPricedError(ApplicationError):
    """Raised when a product the order needs has no price under this price type.

    The storefront shows such a product as "price on request", which is a
    perfectly good state to browse in and an impossible one to order from.
    """


class CartNotFoundError(ApplicationError):
    """Raised when a command needs a cart row that does not exist yet.

    Commands only. A cart is created lazily on the first addition, so
    ``GetCartQuery`` never raises this — it would greet every newly registered
    customer on their first ``/cart``.
    """


class CartRepricedError(ApplicationError):
    """Raised when the cart is no longer worth what the confirmation screen said.

    The gap between the screen showing a total and the command placing the
    order is not seconds: somebody walks away to look up an address and comes
    back half an hour later. Charging more than was shown is the one way this
    shop could look dishonest, so the order is not placed and the screen is
    redrawn with the new total.
    """


class OrderNotFoundError(ApplicationError):
    """Raised when a command or query names an order that does not exist."""


class SearchTermError(ApplicationError):
    """Raised when a search term is too short or too long to run.

    Length is the only thing the application layer checks. How the term is
    normalised and matched is knowledge of the projection and stays there.
    """


class CatalogSourceError(ApplicationError):
    """Raised when the seeder cannot read a catalog snapshot from its source.

    A missing file, unreadable JSON, a shape the source does not recognise.
    The adapter turns all of them into this, so the entry point never sees a
    library exception.
    """


class CatalogSnapshotError(ApplicationError):
    """Raised when a finished import left the projection unusable.

    Today that means one thing: after the sweep, the price type configured as
    the default is not in the projection. Refusing here hands the failure to
    whoever ran the import rather than to the first customer who opens the
    catalog and is told there are no prices.
    """
