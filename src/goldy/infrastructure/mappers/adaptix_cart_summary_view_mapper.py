"""The converter behind what a cart command answers with, built at import time.

A private, module-level ``ConversionRetort`` holds the recipe, and the converter
is generated from it once — the retort caches the code it generates, so a
retort built in a constructor would regenerate it on every command and hold
the cache for nothing.

Every field is a ``link`` with a coercer rather than a linking function of its
own: the two counts are readings of ``Cart.lines`` and the third field is the
converter's second argument, reached through ``from_param``. adaptix links
fields, not properties, which is why ``line_count`` is spelled as the length of
the lines here rather than as the aggregate's property of the same name — the
two say the same thing, and the test beside this module pins that down.
"""

from typing import Final, final, override

from adaptix import P
from adaptix.conversion import ConversionRetort, from_param, link

from goldy.application.common.ports.mappers.cart_summary_view_mapper import (
    CartSummaryViewMapper,
)
from goldy.application.common.views.cart import CartSummaryView
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.product_id import ProductId

_retort: Final[ConversionRetort] = ConversionRetort(
    recipe=[
        link(P[Cart].lines, P[CartSummaryView].line_count, coercer=len),
        link(
            P[Cart].lines,
            P[CartSummaryView].total_quantity,
            coercer=lambda lines: sum(line.quantity.value for line in lines),
        ),
        link(
            from_param("changed_product_id"),
            P[CartSummaryView].changed_product_id,
            coercer=lambda product_id: None if product_id is None else product_id.value,
        ),
    ],
)


@_retort.impl_converter
def _convert_cart_summary(
    cart: Cart,
    changed_product_id: ProductId | None,
) -> CartSummaryView:
    """Contributes its signature; adaptix generates the body that replaces it.

    The body is this docstring and nothing else, because ``impl_converter``
    parses the source and refuses a function that has one — ``pass``, ``...``
    or a docstring are all it accepts. mypy calls that a missing return
    everywhere else and is right everywhere else, so the rule is switched off
    for this module alone, with the reason written beside it in ``mypy.ini``.
    """


@final
class AdaptixCartSummaryViewMapper(CartSummaryViewMapper):
    """Maps a just-changed cart to the counts its command hands back."""

    @override
    def to_view(
        self,
        cart: Cart,
        changed_product_id: ProductId | None,
    ) -> CartSummaryView:
        return _convert_cart_summary(cart, changed_product_id)
