from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.site import SiteFinanceSummaryView


@dataclass(frozen=True, slots=True)
class GetSiteFinanceSummaryQuery(Query[SiteFinanceSummaryView]):
    """The current person's company balances in 1C, through the site."""
