"""``GetCartHandler`` over a stubbed cart, price type and site pricing.

The price type resolver and the personal pricing service are the real ones,
the same choice ``orders/conftest.py`` makes: they are where an unconfigured
price list becomes a refusal and where a stale site link is treated as a
guest, and stubbing them would hide exactly the behaviour these tests exist
to hold.
"""

import pytest

from goldy.application.common.services.personal_pricing import PersonalPricingService
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.queries.carts.get_cart.handler import GetCartHandler
from tests.unit.factories.catalog_factories import make_resolved_price_type
from tests.unit.stubs.cart_query import InMemoryCartQueryGateway
from tests.unit.stubs.catalog import StubPricingReader
from tests.unit.stubs.identity import StubIdentityProvider
from tests.unit.stubs.site import InMemorySiteLinkQueryGateway, ScriptedSitePricing


@pytest.fixture()
def cart_query_gateway() -> InMemoryCartQueryGateway:
    return InMemoryCartQueryGateway()


@pytest.fixture()
def pricing_reader() -> StubPricingReader:
    return StubPricingReader(make_resolved_price_type())


@pytest.fixture()
def site_links() -> InMemorySiteLinkQueryGateway:
    """Nobody is linked to the site unless a test links them."""
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


@pytest.fixture()
def get_cart_handler(
    identity_provider: StubIdentityProvider,
    pricing_reader: StubPricingReader,
    cart_query_gateway: InMemoryCartQueryGateway,
    personal_pricing: PersonalPricingService,
) -> GetCartHandler:
    return GetCartHandler(
        identity_provider,
        PriceTypeResolver(pricing_reader),
        cart_query_gateway,
        personal_pricing,
    )
