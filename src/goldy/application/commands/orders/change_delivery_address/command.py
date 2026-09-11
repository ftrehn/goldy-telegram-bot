from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class ChangeDeliveryAddressCommand(Command[None]):
    """Sending an already placed order somewhere else.

    The one thing about a placed order that may still be edited. A wrong letter
    in an address is the most common reason to cancel an order, and with a
    hundred lines allowed in a cart "cancel and order again" means retyping a
    hundred positions; the address needs no recalculation and does not touch
    the derived total, so the argument for freezing the contents does not apply
    to it.

    The contents stay frozen. There is no command to add, remove or reprice a
    line of a placed order, and writing one would mean reopening the decision
    that the total is a computed property.
    """

    order_id: UUID
    delivery_address: str
