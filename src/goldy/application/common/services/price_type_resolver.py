from typing import Final, final

from goldy.application.common.ports.catalog import PricingReader
from goldy.application.error import (
    PriceTypeNotConfiguredError,
    UnsupportedPriceTypeError,
)
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.users.values.user_id import UserId


@final
class PriceTypeResolver:
    """Resolves which price list a given person buys at.

    A price type is a fact about a person, and the mechanism is visible in the
    signature: the handler names the person — by the id ``IdentityProvider``
    took from the update, the same way every other handler learns who is
    asking — and the resolver joins that person's phone number against the
    bindings 1C exported, falling back to the price list configured for the
    bot. Nothing here is taken from a hidden context; there is no context to
    take it from.

    The reader distinguishes three outcomes and only one of them is ordinary.
    Turning the other two into errors happens once, here, rather than in every
    handler that needs a price type — the same move ``UserProvider`` makes with
    "the gateway returned None", and for the same reason: a handler that forgot
    the check would carry the wrong price list all the way into a snapshot.

    Falling back to the default price list on an unsupported currency is
    deliberately not an option. It would show somebody with a foreign-currency
    price list somebody else's prices and never tell them, which is the one
    failure of this whole stage that looks like dishonesty rather than a bug.
    """

    def __init__(self, pricing_reader: PricingReader) -> None:
        self._pricing_reader: Final[PricingReader] = pricing_reader

    async def resolve_for(self, user_id: UserId) -> PriceTypeId:
        """The price list this person buys at.

        Raises:
            PriceTypeNotConfiguredError: the projection holds neither a binding
                for them nor the price type configured for the bot, which is a
                broken import rather than an ordinary absence - a customer
                without a binding still falls back to the configured default.
            UnsupportedPriceTypeError: their price list is denominated in a
                currency this service does not know, and 1C sent it anyway.
        """
        resolved = await self._pricing_reader.read_price_type_for(user_id)

        if resolved is None:
            msg = f"No price type is configured for user '{user_id}'."
            raise PriceTypeNotConfiguredError(msg)

        if not resolved.is_supported:
            msg = (
                f"Price type '{resolved.price_type_id}' is denominated in a "
                f"currency this shop cannot price in."
            )
            raise UnsupportedPriceTypeError(msg)

        return resolved.price_type_id
