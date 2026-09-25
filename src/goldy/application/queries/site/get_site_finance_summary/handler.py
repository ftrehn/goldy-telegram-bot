from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.site import SiteFinance
from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.common.views.site import SiteFinanceSummaryView
from goldy.application.error import SiteAccountNotLinkedError
from goldy.application.queries.site.get_site_finance_summary.query import (
    GetSiteFinanceSummaryQuery,
)


class GetSiteFinanceSummaryHandler(
    QueryHandler[GetSiteFinanceSummaryQuery, SiteFinanceSummaryView],
):
    """Asks the site for the company's debt, overdue and credit limit.

    Who may see it is the site's decision — a buyer of the company may not,
    its head and accountant may — and the refusal comes back as
    ``SiteFinanceDeniedError`` with the site's reason. The bot only refuses a
    person who is not linked at all, before asking.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        site_link_query_gateway: SiteLinkQueryGateway,
        site_finance: SiteFinance,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._site_link_query_gateway: Final[SiteLinkQueryGateway] = (
            site_link_query_gateway
        )
        self._site_finance: Final[SiteFinance] = site_finance

    @override
    async def handle(self, query: GetSiteFinanceSummaryQuery) -> SiteFinanceSummaryView:
        """The company's balances, as the site reads them from 1C.

        Raises:
            SiteAccountNotLinkedError: the person has no link to the site.
            SiteFinanceDeniedError: the site will not show them the money.
            SiteCustomerNotLinkedError: the site no longer knows the link.
            SiteUnavailableError: neither 1C nor a snapshot answered.
        """
        user_id = await self._identity_provider.get_current_user_id()

        if await self._site_link_query_gateway.read_for(user_id) is None:
            msg = f"User '{user_id}' is not linked to the site."
            raise SiteAccountNotLinkedError(msg)

        return await self._site_finance.summary(str(user_id))
