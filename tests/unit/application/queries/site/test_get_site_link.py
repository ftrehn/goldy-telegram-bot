"""Reading the bot's own copy of the link — the site is never asked here."""

from goldy.application.queries.site.get_site_link.handler import GetSiteLinkHandler
from goldy.application.queries.site.get_site_link.query import GetSiteLinkQuery
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.stubs.site import InMemorySiteLinkQueryGateway, site_link_view

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}


async def test_a_linked_person_gets_the_bots_copy(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    site_links: InMemorySiteLinkQueryGateway,
    get_site_link_handler: GetSiteLinkHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    link = site_link_view()
    site_links.links[customer.id] = link

    view = await get_site_link_handler.handle(GetSiteLinkQuery())

    assert view is link


async def test_an_unlinked_person_gets_nothing(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    get_site_link_handler: GetSiteLinkHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    view = await get_site_link_handler.handle(GetSiteLinkQuery())

    assert view is None
