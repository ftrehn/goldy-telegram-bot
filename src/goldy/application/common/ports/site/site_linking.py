from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from goldy.application.common.views.site import SiteLinkPreviewView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class SiteCustomer:
    """The site's customer a person is linked to, as ``GET /me`` describes them."""

    name: str
    company_name: str | None
    is_wholesale: bool
    finance_access: bool


@dataclass(frozen=True, slots=True)
class SiteLinkRequest:
    """Everything ``POST /links`` needs, gathered by the handler.

    ``subject`` is the bot's ``UserId`` as text — shared by Telegram and MAX,
    so one link serves both. ``label`` and ``phone`` are only for the site's
    cabinet to show which messenger is linked; the site decides nothing by
    them.
    """

    code: str
    subject: str
    platform: MessengerPlatform
    label: str | None
    phone: str | None


class SiteLinking(Protocol):
    """Links a person to their customer account on the site, and unlinks them.

    The site owns the link. The bot asks, the site says yes or no, and the bot
    keeps a copy of the answer on the ``User``.
    """

    @abstractmethod
    async def preview(
        self, code: str, platform: MessengerPlatform
    ) -> SiteLinkPreviewView:
        """Whose account the code leads to, without spending it.

        Raises:
            SiteLinkCodeInvalidError: unknown, expired or already used code.
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError

    @abstractmethod
    async def confirm(self, request: SiteLinkRequest) -> SiteCustomer:
        """Spends the code and links the subject to its customer.

        Raises:
            SiteLinkCodeInvalidError: unknown, expired or already used code.
            SiteLinkForbiddenError: staff of the shop, or a disabled customer.
            SiteSubjectTakenError: the subject is linked to another customer.
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError

    @abstractmethod
    async def revoke(self, subject: str) -> None:
        """Removes the subject's link. Idempotent: no link is the same outcome.

        Raises:
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError
