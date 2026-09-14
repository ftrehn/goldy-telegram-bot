from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class DecreaseCartLineCommand(Command[CartSummaryView]):
    """Takes one piece off a line, and the line off the last piece.

    The ``-`` button therefore carries no quantity and needs to know nothing
    about the current one. A keyboard drawn two seconds ago is allowed to be
    wrong about how many there are; it is not allowed to be the reason a line
    ends up at a quantity nobody asked for.
    """

    product_id: str
