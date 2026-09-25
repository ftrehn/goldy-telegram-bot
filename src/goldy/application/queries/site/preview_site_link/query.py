from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.site import SiteLinkPreviewView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class PreviewSiteLinkQuery(Query[SiteLinkPreviewView]):
    """Whose site account a linking code leads to, before anything is linked.

    ``platform`` is where the code arrived: the site issues a code for one
    platform and refuses it from another.
    """

    code: str
    platform: MessengerPlatform
