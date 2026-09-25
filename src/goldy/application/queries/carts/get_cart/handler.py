import logging
from dataclasses import replace
from decimal import Decimal
from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.carts import CartQueryGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.services.personal_pricing import (
    PersonalPrices,
    PersonalPricingService,
)
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.common.views.cart import CartLineView, CartView, PriceBasis
from goldy.application.common.views.money import MoneyView
from goldy.application.error import SiteUnavailableError
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class GetCartHandler(QueryHandler[GetCartQuery, CartView]):
    """Reads the caller's cart with prices, stock and a total joined in.

    **Never raises ``CartNotFoundError``.** A cart row is created lazily on the
    first addition, so somebody who has just registered has none at all, and an
    error here would greet every new customer on their first ``/cart``. No row
    means an empty view: no lines and a zero total, which the screen draws as
    "your cart is empty" with a button into the catalog.

    The gateway joins the prices and the stock in SQL under this customer's
    price type, which is what makes a new price list reprice a standing cart at
    once instead of leaving old numbers in it. Lines whose product has left the
    catalog come back marked rather than dropped — a total that quietly shrinks
    is worse than one that explains itself.

    A customer linked to the site is then repriced by the site (ADR-0004),
    the same way checkout will price them, so the total on the confirmation
    screen is the total the order is placed at. If the site does not answer,
    the guest prices stay and the view says so in ``price_basis``; the screen
    has to show that, and checkout refuses until the site is back.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        price_type_resolver: PriceTypeResolver,
        cart_query_gateway: CartQueryGateway,
        personal_pricing: PersonalPricingService,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._price_type_resolver: Final[PriceTypeResolver] = price_type_resolver
        self._cart_query_gateway: Final[CartQueryGateway] = cart_query_gateway
        self._personal_pricing: Final[PersonalPricingService] = personal_pricing

    @override
    async def handle(self, query: GetCartQuery) -> CartView:
        user_id = await self._identity_provider.get_current_user_id()
        price_type_id = await self._price_type_resolver.resolve_for(user_id)

        view = await self._cart_query_gateway.read_for(user_id, price_type_id)

        if view is None:
            return CartView(lines=(), total=MoneyView.zero())

        return await self._personalized(user_id, view)

    async def _personalized(self, user_id: UserId, view: CartView) -> CartView:
        """The view at the site's prices for a linked customer, else unchanged."""
        items = [
            (ProductId(value=line.product_id), Quantity(value=line.quantity))
            for line in view.lines
            if line.is_available
        ]

        try:
            personal = await self._personal_pricing.for_user(user_id, items)
        except SiteUnavailableError:
            logger.warning("cart: the site did not price the cart of %s", user_id)
            return replace(view, price_basis=PriceBasis.PERSONAL_UNAVAILABLE)

        if personal is None:
            return view

        lines = tuple(_reprice(line, personal) for line in view.lines)
        return CartView(
            lines=lines,
            total=_total(lines, view.total),
            price_basis=PriceBasis.PERSONAL,
        )


def _reprice(line: CartLineView, personal: PersonalPrices) -> CartLineView:
    """One line at the site's price; a line the site will not price shows none."""
    if not line.is_available:
        return line

    unit = personal.price_of(ProductId(value=line.product_id))

    if unit is None:
        return replace(line, unit_price=None, line_total=None)

    unit_view = MoneyView(amount=unit.amount, currency=unit.currency.value)
    total_view = MoneyView(
        amount=unit.amount * line.quantity, currency=unit_view.currency
    )
    return replace(line, unit_price=unit_view, line_total=total_view)


def _total(lines: tuple[CartLineView, ...], fallback: MoneyView) -> MoneyView:
    """What the priced lines add up to, in their currency."""
    priced = [line.line_total for line in lines if line.line_total is not None]

    if not priced:
        return MoneyView(amount=Decimal("0.00"), currency=fallback.currency)

    return MoneyView(
        amount=sum((total.amount for total in priced), Decimal("0.00")),
        currency=priced[0].currency,
    )
