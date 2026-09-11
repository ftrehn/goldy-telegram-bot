from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class ClearCartCommand(Command[CartSummaryView]):
    """Empties the cart of whoever is writing.

    Carries no fields, and the summary it hands back names no product: this is
    the one cart command that touched all of them.
    """
