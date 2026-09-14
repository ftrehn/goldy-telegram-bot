from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class AddToCartCommand(Command[CartSummaryView]):
    """Puts a product in the cart, adding to whatever is already there.

    Accumulating rather than setting, and **deliberately not idempotent**: a
    double tap leaves a quantity of two, which is visible on the very screen
    that was tapped and undone by the button next to it. Buying idempotence
    with a nonce in every ``callback_data`` would be paying a permanent price
    for a recoverable slip.

    The product is named by its 1C reference as text, because that is what the
    callback of the button carries. The customer is not named at all: the cart
    belongs to whoever is writing, and accepting a user id here would let one
    person fill another's cart.
    """

    product_id: str
    quantity: int = 1
