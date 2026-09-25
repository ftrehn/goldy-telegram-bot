from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, Self, final

MAX_SITE_CUSTOMER_NAME_LENGTH: Final[int] = 200
MAX_SITE_COMPANY_NAME_LENGTH: Final[int] = 255


@final
@dataclass(eq=False, kw_only=True)
class SiteLink:
    """This person's link to their customer account on the site, tkgoldy.ru.

    Not the same thing as linking a messenger account (ADR-0001): that joins a
    second platform to the same person inside the bot, while this joins the
    person to *someone else's* ledger — the site's customer, with the company,
    wholesale prices and 1C balances that come with them. The site is the one
    that decides the link exists; the bot keeps a copy so that a retail
    customer's cart is not a round trip to the site, and so the profile can
    say who they are linked to.

    The subject the site knows this person by is the ``UserId`` itself, shared
    by Telegram and MAX, so a link made from one platform serves the other.

    What is kept is what the profile shows and nothing the bot decides by:
    :attr:`is_wholesale` is the site's answer at the moment of linking, shown
    as a label. Prices are asked of the site every time, never derived from it.

    A mutable dataclass for the reason ``MessengerAccount`` is one: SQLAlchemy
    assigns to these attributes when it loads the row.
    """

    customer_name: str
    company_name: str | None = field(default=None)
    is_wholesale: bool = field(default=False)
    linked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_site(
        cls,
        *,
        customer_name: str,
        company_name: str | None,
        is_wholesale: bool,
    ) -> Self:
        """Builds the copy from what the site answered, trimmed to fit.

        The site's names are whatever a customer typed into its cabinet, so
        they are trimmed to the columns rather than refused: refusing would
        leave a person whose link the site already made unable to see it here.
        An empty name becomes a placeholder for the same reason.
        """
        name = " ".join(customer_name.split())[:MAX_SITE_CUSTOMER_NAME_LENGTH]
        company = " ".join((company_name or "").split())[:MAX_SITE_COMPANY_NAME_LENGTH]

        return cls(
            customer_name=name or "—",
            company_name=company or None,
            is_wholesale=is_wholesale,
        )
