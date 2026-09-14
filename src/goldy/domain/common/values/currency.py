from enum import StrEnum


class Currency(StrEnum):
    """The currency an amount of money is denominated in.

    Persisted as its value in a plain text column rather than a native database
    enum, so adding a currency is a code change and not a migration — the same
    treatment ``MessengerPlatform`` gets.

    The shop sells in roubles, and every order placed today is in ``RUB``. The
    field exists from the first day anyway because price types in 1C are
    routinely denominated per currency, and adding the column to the orders
    table afterwards is a migration over rows that have already been placed.

    The other two members are here for a second reason worth stating, because
    it looks like dead code otherwise: with a single member, "an order may not
    mix currencies" is a rule nothing can violate, no test can express and the
    type checker reads as unreachable. A currency type that cannot represent a
    mismatch is a currency type that is not carrying its weight.
    """

    RUB = "rub"
    USD = "usd"
    EUR = "eur"
