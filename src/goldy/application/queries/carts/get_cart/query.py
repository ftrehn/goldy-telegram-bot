from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.cart import CartView


@dataclass(frozen=True, slots=True)
class GetCartQuery(Query[CartView]):
    """The cart screen of whoever is writing, priced for them right now.

    Carries no fields at all. The cart belongs to the person behind the update
    and the prices follow from the price list they are on, so there is nothing
    for a caller to pass and no way for one to read another's cart.

    Re-read on every render rather than returned by the commands that change
    the cart: prices live in the catalog projection and move without us, while
    a cart lives for days. Anything cached on the way in would eventually show
    a price the shop no longer has.
    """
