from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.common.views.site import SiteLinkView
from goldy.application.queries.site.get_site_link.query import GetSiteLinkQuery


class GetSiteLinkHandler(QueryHandler[GetSiteLinkQuery, SiteLinkView | None]):
    """Reads the bot's copy of the link; the site is not asked."""

    def __init__(
        self,
        identity_provider: IdentityProvider,
        site_link_query_gateway: SiteLinkQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._site_link_query_gateway: Final[SiteLinkQueryGateway] = (
            site_link_query_gateway
        )

    @override
    async def handle(self, query: GetSiteLinkQuery) -> SiteLinkView | None:
        user_id = await self._identity_provider.get_current_user_id()
        return await self._site_link_query_gateway.read_for(user_id)
