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


class CartAlreadyExistsError(ApplicationError):
    """Raised when a cart is inserted for somebody who already has one.

    Comes from the unique index on ``carts.user_id`` rather than from a prior
    read, for the reason ``UserAlreadyExistsError`` does: two simultaneous
    first additions both find nothing and both insert. ``CartProvider`` is
    the one caller, and it answers by taking the cart that won.
    """


class NotificationUndeliverableError(ApplicationError):
    """Raised when a messenger account cannot be written to, now or later.

    The person blocked the bot, deleted their account, or the chat no longer
    exists — answers a messenger gives that do not change on a retry. A sender
    raises this instead of pretending; the dispatcher catches it, counts the
    recipient as skipped and carries on to the next one, because a batch of
    managers must not be abandoned over one of them and a broker redelivery
    would write to everyone the batch already reached a second time.
    """


class NotificationChannelUnavailableError(ApplicationError):
    """Raised when nobody in this process can write to a recipient's messenger.

    A person's notification target names a platform, and the worker holds one
    sender per platform it is configured for. A target this build has no
    sender for is a deployment that lets people choose a messenger nobody can
    write to — a misconfiguration, not an ordinary absence, so the message is
    refused loudly and the broker keeps it until the sender is deployed.
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


class SiteUnavailableError(ApplicationError):
    """Raised when the site did not answer, or answered "not now".

    A timeout, a refused connection, a 5xx, a 429. The same request is worth
    repeating later, which is what distinguishes this from every refusal below:
    a screen says "try again in a minute", the order handover schedules a
    retry, and neither pretends the site said no.
    """


class SiteAccountNotLinkedError(ApplicationError):
    """Raised when something needs a link to the site this person does not have.

    The bot's own answer, before any request: finance and unlinking both start
    from a link, and a person without one gets told how to make it.
    """


class SiteLinkCodeInvalidError(ApplicationError):
    """Raised when the site does not know the linking code, or it has expired.

    Codes live fifteen minutes and are spent on first use, so the ordinary
    cause is a link opened late or twice — the answer is a fresh code from the
    site's cabinet, not a retry.
    """


class SiteLinkForbiddenError(ApplicationError):
    """Raised when the site refuses to link this customer at all.

    Staff of the shop may not be linked (their account sees every company's
    money), and a customer switched off on the site cannot be either. Neither
    is something the person can fix from the bot.
    """


class SiteCustomerNotLinkedError(ApplicationError):
    """Raised when the site says this person is not linked, though we thought so.

    The site is the one that owns the link, and it can go away there — the
    customer pressed "unlink" in the cabinet, the account was merged or
    deleted. The bot's copy is then stale, and whoever catches this treats the
    person as a guest.
    """


class SiteFinanceDeniedError(ApplicationError):
    """Raised when the site will not show this customer the company's money.

    ``reason`` is the site's own: ``no_company``, ``role``, ``not_approved``,
    or ``not_configured`` when the site has no bridge to 1C at all.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason: str = reason


class SiteOrderRejectedError(ApplicationError):
    """Raised when the site refused an order it was handed.

    A refusal, not an outage: prices moved, a position is gone, the credit
    limit is used up. Handing the same order over again gets the same answer,
    so the handover records it and stops. ``code`` is the site's stable code,
    kept for the person who has to sort it out.
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code: str = code


class SiteOrderNotCancellableError(ApplicationError):
    """Raised when the site will not let the customer cancel an order any more.

    A manager has taken it into work or it has been paid; from here only the
    shop can stop it, and the customer is told to call.
    """


class SiteSubjectTakenError(ApplicationError):
    """Raised when the site has this person linked to a different customer.

    The site wants the old link removed first; the linking handler does that
    and asks again, because a person following a fresh code from the cabinet
    has already said which account they mean.
    """
