from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartRepeatView


@dataclass(frozen=True, slots=True)
class RepeatOrderCommand(Command[CartRepeatView]):
    """Fills the cart from an order this customer placed before.

    A cart command rather than an order one, and that is the shape of the whole
    feature: nothing about the order changes, and what comes back describes a
    cart. ADR-0003 leaves no other option — the lines of a placed order are a
    snapshot of a name and a price that were agreed once, so an order re-placed
    from them would be sold at last spring's price. What repeats is the
    shopping, not the document.

    Names the order and nobody else. The customer is not a field for the reason
    it is not one on ``AddToCartCommand``: the cart belongs to whoever is
    writing, and an order somebody else placed is refused by ``IsOrderOwner``
    rather than quietly poured into a stranger's cart.

    **Idempotent, unlike every other way of putting something in this cart.**
    ``AddToCartCommand`` deliberately accumulates, because a double tap on a
    product card is visible on that very card and undone by the button beside
    it. This button is two screens away from the cart and may name ten
    positions, so a second tap that doubled all ten would be discovered at
    checkout; the handler therefore sets the quantities the order had instead of
    adding to them.
    """

    order_id: UUID
