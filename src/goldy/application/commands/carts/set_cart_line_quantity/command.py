from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class SetCartLineQuantityCommand(Command[CartSummaryView]):
    """Sets a line to an absolute quantity, as the keypad screen does.

    Unlike ``+``, this refuses a line that is not there instead of creating
    one. Typing a number is the statement "let there be exactly this many", and
    a missing line means the product was removed since the screen was drawn;
    creating it here would put back what the customer had just taken out, and
    they would only find out after the next redraw.
    """

    product_id: str
    quantity: int
