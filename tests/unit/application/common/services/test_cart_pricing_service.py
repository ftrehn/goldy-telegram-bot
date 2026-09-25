"""Pricing a whole cart in one call: from the catalog, or from the site.

A customer linked to the site is priced by the site (ADR-0004) — the
projection still supplies names, articles and units, and the site supplies the
price by that customer's own terms, recorded on the order under
``PERSONAL_PRICE_TYPE_ID`` so it says where its numbers came from.
"""

import pytest

from goldy.application.common.services.cart_pricing_service import (
    PERSONAL_PRICE_TYPE_ID,
    CartPricing,
    CartPricingService,
)
from goldy.application.common.services.personal_pricing import PersonalPricingService
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.error import ProductNotPricedError, SiteUnavailableError
from tests.unit.factories.catalog_factories import make_resolved_price_type
from tests.unit.factories.shop_factories import (
    make_cart,
    make_money,
    make_priced_product,
    make_product_id,
)
from tests.unit.stubs.catalog import StubPricingReader
from tests.unit.stubs.site import (
    InMemorySiteLinkQueryGateway,
    ScriptedSitePricing,
    site_link_view,
)


@pytest.fixture()
def pricing_reader() -> StubPricingReader:
    return StubPricingReader(make_resolved_price_type())


@pytest.fixture()
def site_links() -> InMemorySiteLinkQueryGateway:
    return InMemorySiteLinkQueryGateway()


@pytest.fixture()
def site_pricing() -> ScriptedSitePricing:
    return ScriptedSitePricing()


@pytest.fixture()
def cart_pricing_service(
    pricing_reader: StubPricingReader,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
) -> CartPricingService:
    return CartPricingService(
        PriceTypeResolver(pricing_reader),
        pricing_reader,
        PersonalPricingService(site_links, site_pricing),
    )


async def test_a_guest_cart_is_priced_straight_from_the_catalog(
    pricing_reader: StubPricingReader,
    cart_pricing_service: CartPricingService,
    site_pricing: ScriptedSitePricing,
) -> None:
    pricing_reader.priced_products = (make_priced_product(1),)
    cart = make_cart({1: 2})

    pricing = await cart_pricing_service.for_cart(cart)

    assert pricing.price_type_id == make_resolved_price_type().price_type_id
    assert pricing.priced_products == pricing_reader.priced_products
    assert site_pricing.calls == []


async def test_a_product_with_no_catalog_price_is_refused_before_the_site_is_asked(
    pricing_reader: StubPricingReader,
    cart_pricing_service: CartPricingService,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
) -> None:
    cart = make_cart({1: 1})
    pricing_reader.unpriced_product_ids = (make_product_id(1),)
    site_links.links[cart.user_id] = site_link_view()

    with pytest.raises(ProductNotPricedError):
        await cart_pricing_service.for_cart(cart)

    assert site_pricing.calls == []


async def test_a_linked_customer_is_priced_by_the_site(
    pricing_reader: StubPricingReader,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
    cart_pricing_service: CartPricingService,
) -> None:
    cart = make_cart({1: 3})
    site_links.links[cart.user_id] = site_link_view()
    pricing_reader.priced_products = (make_priced_product(1, price="10.00"),)
    site_pricing.prices = {make_product_id(1): make_money("15.00")}

    pricing = await cart_pricing_service.for_cart(cart)

    assert pricing.price_type_id == PERSONAL_PRICE_TYPE_ID
    assert len(pricing.priced_products) == 1
    priced = pricing.priced_products[0]
    assert priced.unit_price == make_money("15.00")
    assert priced.product_id == make_product_id(1)
    assert priced.name == make_priced_product(1).name


async def test_a_position_the_site_will_not_sell_the_customer_is_refused(
    pricing_reader: StubPricingReader,
    site_links: InMemorySiteLinkQueryGateway,
    cart_pricing_service: CartPricingService,
) -> None:
    cart = make_cart({1: 1})
    site_links.links[cart.user_id] = site_link_view()
    pricing_reader.priced_products = (make_priced_product(1, price="10.00"),)

    with pytest.raises(ProductNotPricedError):
        await cart_pricing_service.for_cart(cart)


async def test_an_outage_pricing_a_linked_customers_cart_is_not_swallowed(
    pricing_reader: StubPricingReader,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
    cart_pricing_service: CartPricingService,
) -> None:
    """Pricing the order at retail without saying so is worse than asking to retry."""
    cart = make_cart({1: 1})
    site_links.links[cart.user_id] = site_link_view()
    pricing_reader.priced_products = (make_priced_product(1, price="10.00"),)
    site_pricing.errors = [SiteUnavailableError("timed out")]

    with pytest.raises(SiteUnavailableError):
        await cart_pricing_service.for_cart(cart)


def test_the_total_is_the_sum_of_the_priced_lines() -> None:
    cart = make_cart({1: 2, 2: 3})
    pricing = CartPricing(
        price_type_id=make_resolved_price_type().price_type_id,
        priced_products=(
            make_priced_product(1, price="10.00"),
            make_priced_product(2, price="1.50"),
        ),
    )

    assert pricing.total_for(cart) == make_money("10.00").times(
        cart.lines[0].quantity
    ) + (make_money("1.50").times(cart.lines[1].quantity))


def test_an_empty_cart_has_no_total() -> None:
    cart = make_cart()
    pricing = CartPricing(
        price_type_id=make_resolved_price_type().price_type_id, priced_products=()
    )

    assert pricing.total_for(cart) is None


def test_a_line_whose_product_vanished_from_the_catalog_has_no_total() -> None:
    """Distinguished from ``ProductNotPricedError``: this line has no product at all."""
    cart = make_cart({1: 1, 2: 1})
    pricing = CartPricing(
        price_type_id=make_resolved_price_type().price_type_id,
        priced_products=(make_priced_product(1),),
    )

    assert pricing.total_for(cart) is None
