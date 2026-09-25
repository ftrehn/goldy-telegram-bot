from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.site import SiteLinkView


@dataclass(frozen=True, slots=True)
class GetSiteLinkQuery(Query[SiteLinkView | None]):
    """The current person's link to the site, if they have one."""
