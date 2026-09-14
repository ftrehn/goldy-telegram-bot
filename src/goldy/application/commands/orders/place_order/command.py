from dataclasses import dataclass
from decimal import Decimal

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.order import OrderPlacedView


@dataclass(frozen=True, slots=True)
class PlaceOrderCommand(Command[OrderPlacedView]):
    """Turns the cart into an order at the prices the customer was just shown.

    The delivery details are carried as text rather than as domain values
    because they arrive as text: five screens of a dialog, each one holding
    what somebody typed. They become ``DeliveryAddress``, ``Recipient`` and
    ``OrderComment`` inside the handler, which is where their own errors belong.

    :attr:`expected_total` and :attr:`expected_line_count` are what the
    confirmation screen printed, read back off it by the getter. ADR-0003
    reassures that the gap between reading prices and placing an order is
    seconds; for this dialog that is simply untrue, because somebody walks away
    to look up an address and comes back half an hour later. Charging more than
    was shown is the one way this shop could look dishonest, so a disagreement
    refuses the order with ``CartRepricedError`` and the screen is redrawn.

    There is no payment field, no payment status and no payment branch anywhere
    behind this command. Settlement happens outside the bot.
    """

    delivery_address: str
    recipient_first_name: str
    recipient_last_name: str | None
    recipient_phone_number: str
    comment: str | None
    expected_total: Decimal
    expected_line_count: int
