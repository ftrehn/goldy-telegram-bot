from typing import Final

from dishka import Provider, Scope

from goldy.application.common.services.cart_pricing_service import CartPricingService
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.services.purchasable_products_service import (
    PurchasableProductsService,
)
from goldy.application.common.services.user_provider import UserProvider


def services_provider() -> Provider:
    """Application services that sit between the handlers and the ports.

    All four start from ``IdentityProvider``, directly or through each other,
    so this group belongs to a process that serves a person and to no other.
    ``CartPricingService`` owns ``PriceTypeProvider`` rather than sitting beside
    it: that is what keeps ``PlaceOrderHandler`` at five collaborators instead
    of the seven the naive reading needs. ``PurchasableProductsService`` owns
    the same provider for the same reason, so that the repeat handler — which
    already holds a user, an order and a cart — stays inside five.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=UserProvider)
    provider.provide(source=PriceTypeProvider)
    provider.provide(source=CartPricingService)
    provider.provide(source=PurchasableProductsService)
    return provider
