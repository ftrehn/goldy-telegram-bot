from decimal import Decimal
from typing import Any, Final

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.cart import CartView
from goldy.application.common.views.user import UserView
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)
from goldy.presentation.telegram.common.formatting import (
    flag,
    for_message_text,
    format_money,
    format_order_number,
)
from goldy.presentation.telegram.handlers.orders.getters import ORDER_ID_KEY

ADDRESS_KEY: Final[str] = "address"
FIRST_NAME_KEY: Final[str] = "recipient_first_name"
LAST_NAME_KEY: Final[str] = "recipient_last_name"
PHONE_KEY: Final[str] = "phone"
COMMENT_KEY: Final[str] = "comment"

EXPECTED_TOTAL_KEY: Final[str] = "expected_total"
EXPECTED_LINE_COUNT_KEY: Final[str] = "expected_line_count"
"""What the confirmation screen last printed, kept for the command to check.

The order is placed at the numbers the customer was shown, and the two are not
the same thing as the numbers in the cart now: somebody walks off to look up a
flat number and comes back twenty minutes later, by which time an import from
1C may have moved a price. The command compares these against the cart it is
about to turn into an order and refuses a disagreement, so the shop can never
charge more than the screen promised.

Stored as text because ``dialog_data`` is serialised into the FSM storage, and
a ``Decimal`` does not survive the trip — it would come back as a float, which
is the one type a price must never be.
"""

ORDER_NUMBER_KEY: Final[str] = "order_number"
ORDER_PHONE_KEY: Final[str] = "order_phone"
"""What the "done" screen is started with, once there is no dialog under it.

``ORDER_ID_KEY`` travels with them, imported from the orders dialog rather than
spelled again: it is that dialog's key, and the "done" screen hands an order
over by putting the identifier under it. A second constant holding the same
literal would be one rename away from a button that opens the list instead of
the order it names.
"""


def expected_total(manager: DialogManager) -> Decimal:
    total: str = manager.dialog_data[EXPECTED_TOTAL_KEY]

    return Decimal(total)


def expected_line_count(manager: DialogManager) -> int:
    count: int = manager.dialog_data[EXPECTED_LINE_COUNT_KEY]

    return count


def placed_order_id(manager: DialogManager) -> str | None:
    """The identifier of the order this dialog placed, if it placed one.

    Kept beside the number because the two are read at different moments: the
    number is what the screen says, the identifier is what the "open the order"
    button hands to the orders dialog. Text, not a ``UUID`` — ``dialog_data``
    is serialised between updates and start data is serialised into the new
    dialog, and neither survives a ``UUID``.
    """
    order_id: str | None = manager.dialog_data.get(ORDER_ID_KEY)

    return order_id


def placed_order_number(manager: DialogManager) -> str | None:
    """The number of the order this dialog has already placed, if it has.

    The second of the three defences against a double tap, and the weakest of
    them by design: it only ever fires when the screen the first tap should
    have replaced never reached Telegram, so the person is still looking at a
    live "confirm" button after their order was placed.
    """
    number: str | None = manager.dialog_data.get(ORDER_NUMBER_KEY)

    return number


@inject
async def address_getter(
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """Offers where the last order went, for the people who order weekly.

    ``None`` is the ordinary answer for a first order rather than a failure:
    the button simply is not drawn and the screen waits for typing.
    """
    last_address = await sender.send(GetLastDeliveryAddressQuery())

    return {
        "last_address": last_address or "",
        "has_last_address": last_address is not None,
    }


async def phone_getter(user: UserView, **_kwargs: Any) -> dict[str, Any]:
    """The number we already know, offered as a button rather than assumed.

    The recipient need not be the buyer — ordering something for a parent is
    ordinary — so the profile's number is a shortcut and never a default that
    fills itself in.
    """
    return {"phone": user.phone_number}


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """Everything the order is about to be placed with, read back fresh.

    The cart is re-read here rather than carried along from the cart screen,
    which is what makes this the place the totals are taken from. Both numbers
    are left in ``dialog_data`` for the confirmation callback, so what the
    command is checked against is literally what was printed.

    ``repriced`` compares this render against the previous one. It is how a
    refused confirmation explains itself: the command answers a moved price
    with a refusal, the window redraws with the new total, and without the
    notice the only visible change would be a number the person had no reason
    to look at twice.
    """
    cart = await sender.send(GetCartQuery())

    return {
        **typed_details(dialog_manager.dialog_data),
        "count": cart.line_count,
        "total": format_money(cart.total, i18n.locale),
        "repriced": remember_totals(dialog_manager.dialog_data, cart),
    }


def typed_details(dialog_data: dict[str, Any]) -> dict[str, str]:
    """The four screens' worth of typing, as the confirmation prints it back.

    Every one of these is text a person typed at us a moment ago, and this
    screen is the first place it is shown inside a message rather than kept in
    ``dialog_data`` — so this is where :func:`for_message_text` belongs. An
    address containing ``<`` would otherwise make the confirmation unsendable,
    and the order could never be placed at all: there would be no button,
    because there would be no screen.

    The phone number is not quoted because it is not free text by the time it
    arrives here — the callback built a ``PhoneNumber`` out of it, which is
    digits and a leading plus.

    A function of its own so that it can be asserted without a container: the
    getter around it needs a mediator and a dialog manager, and this part needs
    neither.
    """
    comment: str | None = dialog_data.get(COMMENT_KEY)

    return {
        "address": for_message_text(dialog_data[ADDRESS_KEY]),
        "recipient": for_message_text(recipient_name(dialog_data)),
        "phone": dialog_data[PHONE_KEY],
        "has_comment": flag(value=comment is not None),
        "comment": for_message_text(comment or ""),
    }


async def done_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    **_kwargs: Any,
) -> dict[str, Any]:
    """The order number and the number a manager will ring.

    Read from ``start_data`` and not from ``dialog_data``: this screen is
    reached by starting the dialog over on an empty stack, so the data of the
    checkout that placed the order is gone by the time it renders.

    ``has_order_id`` guards the button that opens the order rather than the
    identifier being assumed present. The screen can be reached with an order
    number and nothing else — that is what the repeat-tap path hands it when
    the first attempt's identifier was never written down — and a button that
    started the orders dialog with no order would open the list while calling
    itself "open the order".
    """
    started_with = _started_with(dialog_manager)
    number: str = started_with.get(ORDER_NUMBER_KEY, "")

    return {
        "number": format_order_number(i18n, number),
        "phone": started_with.get(ORDER_PHONE_KEY, ""),
        "has_order_id": bool(started_with.get(ORDER_ID_KEY)),
    }


def _started_with(manager: DialogManager) -> dict[str, Any]:
    """The dictionary this dialog was started with, or an empty one.

    ``start_data`` is typed as anything a dialog may be started with, and only
    a mapping means anything here — narrowing it once keeps the getter from
    deciding what to do about a list of integers.
    """
    data = manager.start_data

    return data if isinstance(data, dict) else {}


def recipient_name(dialog_data: dict[str, Any]) -> str:
    """The recipient as one line, from the two fields it was typed as."""
    first_name: str = dialog_data[FIRST_NAME_KEY]
    last_name: str | None = dialog_data.get(LAST_NAME_KEY)

    if last_name is None:
        return first_name

    return f"{first_name} {last_name}"


def remember_totals(dialog_data: dict[str, Any], cart: CartView) -> bool:
    """Writes down what is being shown, and says whether it moved.

    Takes the window's own data rather than the manager holding it, because
    what it does is arithmetic over two renders and nothing else — which is
    the whole of the repricing notice and the only part of this dialog that
    can be wrong without anybody seeing it happen.

    The first render has nothing to compare against and reports no change: a
    cart cannot have been repriced before it was ever printed, and claiming
    otherwise would put a warning on every checkout.
    """
    previous_total = dialog_data.get(EXPECTED_TOTAL_KEY)
    previous_count = dialog_data.get(EXPECTED_LINE_COUNT_KEY)

    total = str(cart.total.amount)
    dialog_data[EXPECTED_TOTAL_KEY] = total
    dialog_data[EXPECTED_LINE_COUNT_KEY] = cart.line_count

    if previous_total is None:
        return False

    return previous_total != total or previous_count != cart.line_count
