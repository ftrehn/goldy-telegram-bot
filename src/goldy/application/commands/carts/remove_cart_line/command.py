from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class RemoveCartLineCommand(Command[CartSummaryView]):
    """Takes one product out of the cart entirely."""

    product_id: str
