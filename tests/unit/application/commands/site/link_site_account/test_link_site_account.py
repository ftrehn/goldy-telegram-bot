"""Linking to the site: the site is asked first, and the bot follows its answer.

``subject_taken`` is the interesting branch — the person just followed a fresh
code from the cabinet of the account they want, which says clearly enough
which one they mean, so the old link is dropped and the same code is spent
again rather than the person being told to start over.
"""

import pytest

from goldy.application.commands.site.link_site_account.command import (
    LinkSiteAccountCommand,
)
from goldy.application.commands.site.link_site_account.handler import (
    LinkSiteAccountHandler,
)
from goldy.application.error import (
    SiteLinkCodeInvalidError,
    SiteLinkForbiddenError,
    SiteSubjectTakenError,
)
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.factories.domain_factories import make_account
from tests.unit.stubs.site import ScriptedSiteLinking

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}
CODE: str = "abcdefghijklmnopqrst"


async def test_linking_asks_the_site_and_keeps_its_answer(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    view = await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    assert view.customer_name == site_linking.customer.name
    assert view.company_name == site_linking.customer.company_name
    assert view.is_wholesale == site_linking.customer.is_wholesale
    assert customer.is_site_linked is True
    assert customer.site_link is not None
    assert customer.site_link.customer_name == site_linking.customer.name


async def test_the_request_carries_the_subject_and_the_customers_phone(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    request = site_linking.confirmations[0]
    assert request.subject == str(customer.id)
    assert request.phone == str(customer.phone_number)
    assert request.platform is MessengerPlatform.TELEGRAM


async def test_the_code_is_normalized_before_it_is_sent(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    await link_site_account_handler.handle(
        LinkSiteAccountCommand(
            code=f"  {CODE.upper()}  ", platform=MessengerPlatform.TELEGRAM
        ),
    )

    assert site_linking.confirmations[0].code == CODE


async def test_an_invalid_code_never_reaches_the_site(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    """A typo is worth catching here.

    A request per typo is a request against the site's rate limit for every
    other customer of the bot.
    """
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(SiteLinkCodeInvalidError):
        await link_site_account_handler.handle(
            LinkSiteAccountCommand(
                code="not a code", platform=MessengerPlatform.TELEGRAM
            ),
        )

    assert site_linking.confirmations == []
    assert customer.is_site_linked is False


async def test_the_label_names_the_platform_and_the_handle(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    assert site_linking.confirmations[0].label == "Telegram @c3equalz"


async def test_the_label_has_no_handle_when_the_account_has_none(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(phone_number="+79991111111", external_id="111")
    customer.accounts[0].username = None
    acting_as(customer.id)

    await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    assert site_linking.confirmations[0].label == "Telegram"


async def test_the_max_label_is_spelled_in_capitals(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    """Not ``.capitalize()``'s "Max" — the platform is spelled MAX everywhere else."""
    customer = await seed_user(**CUSTOMER)
    customer.link_account(
        make_account(MessengerPlatform.MAX, "987654", username="ivanov")
    )
    acting_as(customer.id)

    await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.MAX),
    )

    assert site_linking.confirmations[0].label == "MAX @ivanov"


async def test_a_subject_already_linked_elsewhere_is_relinked_to_the_fresh_code(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    """A fresh code from the cabinet already says which account is meant."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    site_linking.errors = [SiteSubjectTakenError("linked to another customer")]

    view = await link_site_account_handler.handle(
        LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    assert site_linking.revoked == [str(customer.id)]
    assert len(site_linking.confirmations) == 2
    assert view.customer_name == site_linking.customer.name
    assert customer.is_site_linked is True


async def test_a_refusal_for_another_reason_is_not_treated_as_subject_taken(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_linking: ScriptedSiteLinking,
    link_site_account_handler: LinkSiteAccountHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    site_linking.errors = [SiteLinkForbiddenError("staff of the shop")]

    with pytest.raises(SiteLinkForbiddenError):
        await link_site_account_handler.handle(
            LinkSiteAccountCommand(code=CODE, platform=MessengerPlatform.TELEGRAM),
        )

    assert site_linking.revoked == []
    assert customer.is_site_linked is False
