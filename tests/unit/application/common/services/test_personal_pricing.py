"""Asking the site for prices, and only for a person the bot's copy links.

Whether to ask at all is read from the bot's copy of the link, never from the
site — a retail customer's cart must never wait on a request that was never
going to answer anything but "no link".
"""

import pytest

from goldy.application.common.services.personal_pricing import (
    PersonalPrices,
    PersonalPricingService,
)
from goldy.application.error import SiteCustomerNotLinkedError, SiteUnavailableError
from goldy.domain.catalog.values.product_id import ProductId
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.factories.shop_factories import make_money, make_product_id, make_quantity
from tests.unit.stubs.site import (
    InMemorySiteLinkQueryGateway,
    ScriptedSitePricing,
    site_link_view,
)


@pytest.fixture()
def site_links() -> InMemorySiteLinkQueryGateway:
    return InMemorySiteLinkQueryGateway()


@pytest.fixture()
def site_pricing() -> ScriptedSitePricing:
    return ScriptedSitePricing()


@pytest.fixture()
def personal_pricing(
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
) -> PersonalPricingService:
    return PersonalPricingService(site_links, site_pricing)


async def test_a_guest_is_answered_with_no_prices_at_all(
    personal_pricing: PersonalPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    user_id = make_user_id()

    prices = await personal_pricing.for_user(
        user_id, [(make_product_id(1), make_quantity())]
    )

    assert prices is None
    assert site_pricing.calls == []


async def test_is_linked_reflects_the_bots_copy_of_the_link(
    site_links: InMemorySiteLinkQueryGateway,
    personal_pricing: PersonalPricingService,
) -> None:
    user_id = make_user_id()

    assert await personal_pricing.is_linked(user_id) is False

    site_links.links[user_id] = site_link_view()

    assert await personal_pricing.is_linked(user_id) is True


async def test_a_linked_customer_with_nothing_to_price_is_not_asked(
    site_links: InMemorySiteLinkQueryGateway,
    personal_pricing: PersonalPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    user_id = make_user_id()
    site_links.links[user_id] = site_link_view()

    prices = await personal_pricing.for_user(user_id, [])

    assert prices == PersonalPrices(prices={})
    assert site_pricing.calls == []


async def test_a_linked_customer_is_priced_for_every_item_in_one_call(
    site_links: InMemorySiteLinkQueryGateway,
    personal_pricing: PersonalPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    user_id = make_user_id()
    site_links.links[user_id] = site_link_view()
    priced = make_product_id(1)
    unavailable = make_product_id(2)
    site_pricing.prices = {priced: make_money("15.00")}

    prices = await personal_pricing.for_user(
        user_id,
        [(priced, make_quantity(2)), (unavailable, make_quantity(1))],
    )

    assert prices is not None
    assert prices.price_of(priced) == make_money("15.00")
    assert prices.price_of(unavailable) is None
    subject, items = site_pricing.calls[0]
    assert subject == str(user_id)
    assert {item.product_id for item in items} == {priced, unavailable}


def test_a_product_that_was_never_requested_has_no_price() -> None:
    prices = PersonalPrices(prices={})

    assert prices.price_of(ProductId(value="unknown")) is None


async def test_the_site_forgetting_the_link_is_treated_as_a_guest(
    site_links: InMemorySiteLinkQueryGateway,
    personal_pricing: PersonalPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    """The bot's copy said linked; the site itself now disagrees.

    That happens when the customer unlinked in the cabinet, and the person is
    shown the guest prices — exactly what the site would charge them now.
    """
    user_id = make_user_id()
    site_links.links[user_id] = site_link_view()
    site_pricing.errors = [SiteCustomerNotLinkedError("no longer linked")]

    prices = await personal_pricing.for_user(
        user_id, [(make_product_id(1), make_quantity())]
    )

    assert prices is None


async def test_an_outage_pricing_a_linked_customer_is_not_swallowed(
    site_links: InMemorySiteLinkQueryGateway,
    personal_pricing: PersonalPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    """Pricing at retail without saying so is the quiet kind of wrong.

    So an outage is not swallowed into an ordinary "guest" answer.
    """
    user_id = make_user_id()
    site_links.links[user_id] = site_link_view()
    site_pricing.errors = [SiteUnavailableError("timed out")]

    with pytest.raises(SiteUnavailableError):
        await personal_pricing.for_user(user_id, [(make_product_id(1), make_quantity())])
