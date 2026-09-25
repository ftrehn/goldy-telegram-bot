from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.site import SiteLinking
from goldy.application.common.services.site_link_code import normalize_link_code
from goldy.application.common.views.site import SiteLinkPreviewView
from goldy.application.queries.site.preview_site_link.query import PreviewSiteLinkQuery


class PreviewSiteLinkHandler(QueryHandler[PreviewSiteLinkQuery, SiteLinkPreviewView]):
    """Asks the site whose account the code leads to, without spending it.

    A query although it goes out to the site: it changes nothing on either
    side, and the person decides on its answer whether to link at all.
    """

    def __init__(self, site_linking: SiteLinking) -> None:
        self._site_linking: Final[SiteLinking] = site_linking

    @override
    async def handle(self, query: PreviewSiteLinkQuery) -> SiteLinkPreviewView:
        """The masked owner of the code, as the site reports it.

        Raises:
            SiteLinkCodeInvalidError: not a code, or the site does not know it.
            SiteUnavailableError: the site did not answer.
        """
        return await self._site_linking.preview(
            normalize_link_code(query.code),
            query.platform,
        )
