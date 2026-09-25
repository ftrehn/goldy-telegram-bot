from enum import StrEnum


class CancellationInitiator(StrEnum):
    """Who stopped the order.

    A field rather than two statuses: the customer changing their mind and the
    shop refusing are one fact with two authors, and splitting them would make
    every reader match on two values where one question is being asked.
    """

    CUSTOMER = "customer"
    MANAGER = "manager"
    SHOP = "shop"
    """The shop, through the site the order was handed over to (ADR-0004).

    Nobody in the bot pressed anything: a manager cancelled the order in the
    site's admin or in 1C, and the status came back with the order feed. There
    is therefore no person to record and no reason to require — the site's
    feed carries neither.
    """
