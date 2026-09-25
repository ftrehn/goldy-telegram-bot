"""Company balances from 1C, through the site — refused before asking if unlinked."""

import pytest

from goldy.application.error import SiteAccountNotLinkedError, SiteFinanceDeniedError
from goldy.application.queries.site.get_site_finance_summary.handler import (
    GetSiteFinanceSummaryHandler,
)
from goldy.application.queries.site.get_site_finance_summary.query import (
    GetSiteFinanceSummaryQuery,
)
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.stubs.site import InMemorySiteLinkQueryGateway, site_link_view
from tests.unit.stubs.site_finance import ScriptedSiteFinance

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}


async def test_an_unlinked_person_is_refused_before_the_site_is_asked(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_finance: ScriptedSiteFinance,
    get_site_finance_summary_handler: GetSiteFinanceSummaryHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(SiteAccountNotLinkedError):
        await get_site_finance_summary_handler.handle(GetSiteFinanceSummaryQuery())

    assert site_finance.calls == []


async def test_a_linked_person_gets_the_sites_summary(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_links: InMemorySiteLinkQueryGateway,
    site_finance: ScriptedSiteFinance,
    get_site_finance_summary_handler: GetSiteFinanceSummaryHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    site_links.links[customer.id] = site_link_view()

    view = await get_site_finance_summary_handler.handle(GetSiteFinanceSummaryQuery())

    assert view is site_finance.answer
    assert site_finance.calls == [str(customer.id)]


async def test_the_site_may_still_deny_a_linked_persons_own_request(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_links: InMemorySiteLinkQueryGateway,
    site_finance: ScriptedSiteFinance,
    get_site_finance_summary_handler: GetSiteFinanceSummaryHandler,
) -> None:
    """A buyer of the company may not see its money; its head and accountant may."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    site_links.links[customer.id] = site_link_view()
    site_finance.errors = [SiteFinanceDeniedError("no such role", reason="role")]

    with pytest.raises(SiteFinanceDeniedError) as excinfo:
        await get_site_finance_summary_handler.handle(GetSiteFinanceSummaryQuery())

    assert excinfo.value.reason == "role"
