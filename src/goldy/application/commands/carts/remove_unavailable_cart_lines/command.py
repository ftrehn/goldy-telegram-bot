from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.cart import CartSummaryView


@dataclass(frozen=True, slots=True)
class RemoveUnavailableCartLinesCommand(Command[CartSummaryView]):
    """Drops every line whose product has left the catalog.

    What the "remove unavailable" button on the cart screen sends. A product
    can be withdrawn between being added and being ordered, and the cart shows
    such lines marked rather than hiding them, so this is the one move that
    unblocks checkout without the customer having to work out which of eight
    positions is the problem.

    Names no product: the customer is not choosing which line to drop, they are
    accepting all of them at once. Which is why this is idempotent by
    construction — running it on a tidy cart finds nothing to remove and
    succeeds, since "leave me only what can be ordered" is already true.
    """
