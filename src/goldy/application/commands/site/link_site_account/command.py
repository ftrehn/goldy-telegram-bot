from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.site import SiteLinkView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class LinkSiteAccountCommand(Command[SiteLinkView]):
    """The person agreed: link them to the site account the code leads to.

    Sent only after the person saw the preview and pressed "yes" — the
    confirmation step is the defence against somebody sending a victim a
    link with the attacker's own code.
    """

    code: str
    platform: MessengerPlatform
