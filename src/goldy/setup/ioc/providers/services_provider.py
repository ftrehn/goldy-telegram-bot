from typing import Final

from dishka import Provider, Scope

from goldy.application.common.services.cart_pricing_service import CartPricingService
from goldy.application.common.services.cart_provider import CartProvider
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.common.services.purchasable_products_service import (
    PurchasableProductsService,
)
from goldy.application.common.services.user_provider import UserProvider


def services_provider() -> Provider:
    """Application services that sit between the handlers and the ports.

    ``UserProvider`` and ``CartProvider`` start from ``IdentityProvider``, so
    this group belongs to a process that serves a person and to no other.
    ``PriceTypeResolver`` takes a user id rather than the identity provider,
    and ``CartPricingService`` resolves the price list of the cart's owner
    through it; both sit here all the same, because nothing but a person's
    request ever prices a cart. ``CartPricingService`` owns the resolver and
    the reader rather than sitting beside them: that is what keeps
    ``PlaceOrderHandler`` under the collaborator ceiling.
    ``PurchasableProductsService`` owns the same pair for the same reason, so
    that the repeat handler — which already holds a user, an order and a cart
    — stays inside five.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=UserProvider)
    provider.provide(source=CartProvider)
    provider.provide(source=PriceTypeResolver)
    provider.provide(source=CartPricingService)
    provider.provide(source=PurchasableProductsService)
    return provider
