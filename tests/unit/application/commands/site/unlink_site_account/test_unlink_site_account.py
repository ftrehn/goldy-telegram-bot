"""Unlinking: the site is asked first, and the bot's copy only follows if it agreed.

In that order and not the other — a link the site still holds is the bot's
token acting as that customer, and forgetting it only on our side would leave
exactly that behind.
"""

import pytest

from goldy.application.commands.site.unlink_site_account.command import (
    UnlinkSiteAccountCommand,
)
from goldy.application.commands.site.unlink_site_account.handler import (
    UnlinkSiteAccountHandler,
)
from goldy.application.error import SiteAccountNotLinkedError, SiteUnavailableError
from goldy.domain.users.entities.site_link import SiteLink
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.stubs.site import ScriptedSiteLinking

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}


def _link() -> SiteLink:
    return SiteLink.from_site(
        customer_name="Иван Иванов",
        company_name="Ромашка",
        is_wholesale=True,
    )


async def test_unlinking_revokes_on_the_site_and_then_locally(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    unlink_site_account_handler: UnlinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    customer.link_site_account(_link())
    acting_as(customer.id)

    await unlink_site_account_handler.handle(UnlinkSiteAccountCommand())

    assert site_linking.revoked == [str(customer.id)]
    assert customer.is_site_linked is False


async def test_a_person_with_no_link_is_refused_before_the_site_is_asked(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    unlink_site_account_handler: UnlinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(SiteAccountNotLinkedError):
        await unlink_site_account_handler.handle(UnlinkSiteAccountCommand())

    assert site_linking.revoked == []


async def test_a_failed_revoke_leaves_the_local_copy_linked(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    unlink_site_account_handler: UnlinkSiteAccountHandler,
) -> None:
    """The bot's token would still act as that customer if it forgot on our side alone."""
    customer = await seed_user(**CUSTOMER)
    link = _link()
    customer.link_site_account(link)
    acting_as(customer.id)
    site_linking.revoke_errors = [SiteUnavailableError("timed out")]

    with pytest.raises(SiteUnavailableError):
        await unlink_site_account_handler.handle(UnlinkSiteAccountCommand())

    assert customer.is_site_linked is True
    assert customer.site_link is link
