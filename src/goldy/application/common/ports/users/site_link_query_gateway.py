from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.views.site import SiteLinkView
    from goldy.domain.users.values.user_id import UserId


class SiteLinkQueryGateway(Protocol):
    """Reads whether a person is linked to the site, without loading them.

    The storefront asks this on every cart render, and a whole ``User`` with
    its accounts is the wrong price for one yes or no.
    """

    @abstractmethod
    async def read_for(self, user_id: UserId) -> SiteLinkView | None:
        raise NotImplementedError
