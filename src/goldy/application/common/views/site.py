from dataclasses import dataclass
from datetime import datetime

from goldy.application.common.views.money import MoneyView


@dataclass(frozen=True, slots=True)
class SiteLinkPreviewView:
    """Whose account a linking code leads to, masked the way the site masks it.

    Shown to the person before anything is linked: "Иван И., i***@mail.ru,
    ТД «Ромашка» — this is you?". The step is what stops somebody who sent a
    victim their own code from getting the victim's messenger in their account.
    """

    customer_name: str
    email: str | None
    company_name: str | None


@dataclass(frozen=True, slots=True)
class SiteLinkView:
    """The bot's copy of a person's link to the site, for the profile screen."""

    customer_name: str
    company_name: str | None
    is_wholesale: bool
    linked_at: datetime


@dataclass(frozen=True, slots=True)
class SiteFinanceSummaryView:
    """The top of the site's "Finance" section, for one linked customer.

    Every amount is optional and ``None`` means *unknown*, never zero:
    ``credit_limit`` is ``None`` when 1C does not keep a limit at all, and a
    zero there would read as "no credit". :attr:`is_stale` — 1C did not
    answer and this is its last snapshot, as of :attr:`as_of`;
    :attr:`is_partial` — not every partner of the company answered, so the
    sum is not the debt; :attr:`erp_linked` false — the company is not matched
    with 1C and there are no figures at all. The screen has to say each of
    these out loud; figures without them read as the truth.
    """

    company_name: str | None
    erp_linked: bool
    debt: MoneyView | None
    advance: MoneyView | None
    overdue: MoneyView | None
    max_days_overdue: int | None
    credit_limit: MoneyView | None
    credit_available: MoneyView | None
    as_of: datetime | None
    is_stale: bool
    is_partial: bool
