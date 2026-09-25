import logging
from typing import Final, override

from goldy.application.commands.site.link_site_account.command import (
    LinkSiteAccountCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.site import SiteCustomer, SiteLinkRequest, SiteLinking
from goldy.application.common.services.site_link_code import normalize_link_code
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.site import SiteLinkView
from goldy.application.error import SiteSubjectTakenError
from goldy.domain.users.entities.site_link import SiteLink
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.messenger_platform import MessengerPlatform

logger: Final[logging.Logger] = logging.getLogger(__name__)


class LinkSiteAccountHandler(CommandHandler[LinkSiteAccountCommand, SiteLinkView]):
    """Links the person to their site account and keeps a copy of the link.

    The subject is the ``UserId``, shared by every platform the person writes
    from, so a link made in Telegram serves MAX too.

    ``subject_taken`` means this person is already linked to *another* site
    customer. They have just followed a fresh code from the cabinet of the
    account they want, which says clearly enough which one they mean, so the
    old link is removed and the confirmation repeated. The code survives the
    first refusal: the site spends it only in the transaction that links.

    The site is asked before the bot writes anything. If the commit of the
    copy then fails, the site holds a link the bot does not know of, and the
    next attempt replaces it — the site treats relinking the same subject to
    the same customer as a replacement, not an error.
    """

    def __init__(self, user_provider: UserProvider, site_linking: SiteLinking) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._site_linking: Final[SiteLinking] = site_linking

    @override
    async def handle(self, command: LinkSiteAccountCommand) -> SiteLinkView:
        """Spends the code on the site and keeps a copy of the link on the user.

        Raises:
            SiteLinkCodeInvalidError: not a code, unknown, expired or used.
            SiteLinkForbiddenError: staff of the shop, or a disabled customer.
            SiteUnavailableError: the site did not answer.
        """
        user = await self._user_provider.current()
        request = SiteLinkRequest(
            code=normalize_link_code(command.code),
            subject=str(user.id),
            platform=command.platform,
            label=_label(user, command.platform),
            phone=str(user.phone_number),
        )

        customer = await self._confirm(request)
        link = SiteLink.from_site(
            customer_name=customer.name,
            company_name=customer.company_name,
            is_wholesale=customer.is_wholesale,
        )
        user.link_site_account(link)

        return SiteLinkView(
            customer_name=link.customer_name,
            company_name=link.company_name,
            is_wholesale=link.is_wholesale,
            linked_at=link.linked_at,
        )

    async def _confirm(self, request: SiteLinkRequest) -> SiteCustomer:
        try:
            return await self._site_linking.confirm(request)
        except SiteSubjectTakenError:
            logger.info(
                "site link: %s was linked to another customer, relinking",
                request.subject,
            )
            await self._site_linking.revoke(request.subject)
            return await self._site_linking.confirm(request)


def _label(user: User, platform: MessengerPlatform) -> str:
    """What the site's cabinet shows for this link: "Telegram @ivanov"."""
    account = user.account_for(platform)
    name = platform.value.capitalize() if platform is not MessengerPlatform.MAX else "MAX"

    if account is not None and account.username is not None:
        return f"{name} @{account.username}"

    return name
