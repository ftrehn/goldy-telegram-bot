"""The converter behind what a cart command answers with, built at import time.

Every field goes through a ``link_function``, because adaptix links fields and
not paths: two of the three are properties of the aggregate rather than fields
of it, and the third does not come off the aggregate at all. ``ProductId`` needs
one for the reason ``UserId`` does — a value the view carries as text is not
text in the domain, and adaptix does not unwrap it on its own.

``impl_converter`` rather than ``get_converter``: the mapper takes two
arguments. The first parameter of a linking function is the source model, and
the parameters after it are matched by name against the converter's own extra
parameters, which is how ``changed_product_id`` reaches the field of the same
name.
"""

from typing import final, override

from adaptix import P
from adaptix.conversion import impl_converter, link_function

from goldy.application.common.ports.mappers.cart_summary_view_mapper import (
    CartSummaryViewMapper,
)
from goldy.application.common.views.cart import CartSummaryView
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.product_id import ProductId


def _line_count_of(cart: Cart) -> int:
    return cart.line_count


def _total_quantity_of(cart: Cart) -> int:
    return cart.total_quantity


def _changed_product_id_of(
    _cart: Cart,
    changed_product_id: ProductId | None,
) -> str | None:
    """Unwraps the product the command touched, or reports that all of them were.

    The cart is taken and ignored on purpose: adaptix hands the source model to
    the first parameter of every linking function, and this one is answered
    entirely from the converter's second argument. The aggregate could not
    answer it anyway — it does not know which of its lines was just changed.
    """
    return changed_product_id.value if changed_product_id is not None else None


@impl_converter(
    recipe=[
        link_function(_line_count_of, P[CartSummaryView].line_count),
        link_function(_total_quantity_of, P[CartSummaryView].total_quantity),
        link_function(_changed_product_id_of, P[CartSummaryView].changed_product_id),
    ],
)
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
    """Maps a just-changed cart to the counts its command hands back.

    The converter is module-level for the reason the other adaptix mappers give:
    the retort caches generated code, so building it per instance would
    regenerate it on every command.
    """

    @override
    def to_view(
        self,
        cart: Cart,
        changed_product_id: ProductId | None,
    ) -> CartSummaryView:
        return _convert_cart_summary(cart, changed_product_id)
