from typing import Final, final

from goldy.application.common.ports.catalog import PricingGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.error import (
    PriceTypeNotConfiguredError,
    UnsupportedPriceTypeError,
)
from goldy.domain.catalog.values.price_type_id import PriceTypeId


@final
class PriceTypeProvider:
    """Resolves which price list the person in front of us buys at.

    The gateway distinguishes three outcomes and only one of them is ordinary.
    Turning the other two into errors happens once, here, rather than in every
    handler that needs a price type — the same move ``UserProvider`` makes with
    "the gateway returned None", and for the same reason: a handler that forgot
    the check would carry the wrong price list all the way into a snapshot.

    Falling back to the default price list on an unsupported currency is
    deliberately not an option. It would show somebody with a foreign-currency
    price list somebody else's prices and never tell them, which is the one
    failure of this whole stage that looks like dishonesty rather than a bug.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        pricing_gateway: PricingGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._pricing_gateway: Final[PricingGateway] = pricing_gateway

    async def current(self) -> PriceTypeId:
        """The price list of whoever is running this request.

        There is no ``for_user`` counterpart to ``UserProvider.by_id``, and the
        asymmetry is deliberate: a price list is only ever resolved for the
        person the request belongs to. Naming somebody else would be a way to
        show one customer another customer's prices.

        Raises:
            PriceTypeNotConfiguredError: the projection holds neither a binding
                for them nor the price type configured for the bot, which is a
                broken import rather than an ordinary absence - a customer
                without a binding still falls back to the configured default.
            UnsupportedPriceTypeError: their price list is denominated in a
                currency this service does not know, and 1C sent it anyway.
        """
        user_id = await self._identity_provider.get_current_user_id()
        view = await self._pricing_gateway.read_price_type_for(user_id)

        if view is None:
            msg = f"No price type is configured for user '{user_id}'."
            raise PriceTypeNotConfiguredError(msg)

        if not view.is_supported:
            msg = (
                f"Price type '{view.price_type_id}' is denominated in a "
                f"currency this shop cannot price in."
            )
            raise UnsupportedPriceTypeError(msg)

        return PriceTypeId(value=view.price_type_id)
