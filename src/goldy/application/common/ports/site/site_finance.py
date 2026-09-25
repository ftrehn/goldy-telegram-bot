from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.views.site import SiteFinanceSummaryView


class SiteFinance(Protocol):
    """Reads the 1C balances of a linked customer's company, through the site."""

    @abstractmethod
    async def summary(self, subject: str) -> SiteFinanceSummaryView:
        """Debt, overdue and credit limit, summed over the company's partners.

        Raises:
            SiteFinanceDeniedError: the customer may not see the company's money.
            SiteCustomerNotLinkedError: the site no longer knows the subject.
            SiteUnavailableError: neither 1C nor a snapshot answered.
        """
        raise NotImplementedError
