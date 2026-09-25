from typing import Final, override

from goldy.application.commands.site.unlink_site_account.command import (
    UnlinkSiteAccountCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.site import SiteLinking
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.error import SiteAccountNotLinkedError


class UnlinkSiteAccountHandler(CommandHandler[UnlinkSiteAccountCommand, None]):
    """Removes the link on the site first, then the bot's copy.

    In that order and not the other: a link the site still holds is the bot's
    token acting as that customer — their prices, their company's money — and
    forgetting it only on our side would leave exactly that behind. If the
    site does not answer, nothing is changed here and the person is told to
    try again.
    """

    def __init__(self, user_provider: UserProvider, site_linking: SiteLinking) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._site_linking: Final[SiteLinking] = site_linking

    @override
    async def handle(self, command: UnlinkSiteAccountCommand) -> None:
        """Removes the link on the site first, then the bot's copy.

        Raises:
            SiteAccountNotLinkedError: there is no link to remove.
            SiteUnavailableError: the site did not answer.
        """
        user = await self._user_provider.current()

        if not user.is_site_linked:
            msg = f"User '{user.id}' is not linked to the site."
            raise SiteAccountNotLinkedError(msg)

        await self._site_linking.revoke(str(user.id))
        user.unlink_site_account()
