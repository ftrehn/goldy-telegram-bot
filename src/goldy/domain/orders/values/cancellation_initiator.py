from enum import StrEnum


class CancellationInitiator(StrEnum):
    """Who stopped the order.

    A field rather than two statuses: the customer changing their mind and the
    shop refusing are one fact with two authors, and splitting them would make
    every reader match on two values where one question is being asked.
    """

    CUSTOMER = "customer"
    MANAGER = "manager"
