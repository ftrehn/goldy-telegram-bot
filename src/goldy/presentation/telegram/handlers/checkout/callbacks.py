from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.orders.place_order.command import PlaceOrderCommand
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)
from goldy.domain.carts.errors import EmptyCartError
from goldy.domain.common.error import AppError
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.presentation.telegram.handlers.checkout.getters import (
    ADDRESS_KEY,
    COMMENT_KEY,
    FIRST_NAME_KEY,
    LAST_NAME_KEY,
    ORDER_NUMBER_KEY,
    ORDER_PHONE_KEY,
    PHONE_KEY,
    expected_line_count,
    expected_total,
    placed_order_id,
    placed_order_number,
)
from goldy.presentation.telegram.handlers.checkout.states import CheckoutStates
from goldy.presentation.telegram.handlers.orders.getters import ORDER_ID_KEY
from goldy.presentation.telegram.handlers.orders.states import OrdersStates
from goldy.presentation.telegram.middlewares.auth_middleware import USER_KEY


async def on_address_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
) -> None:
    """Takes the address, and judges it here rather than five screens later.

    ``DeliveryAddress`` is built now so that "home" is refused on the screen
    that asked for an address, where the answer is one line of typing away. The
    command would refuse it too, at the end of a walk through four more
    screens, by which point the person has to work out which of them was wrong.
    """
    address = DeliveryAddress(value=(message.text or "").strip())

    manager.dialog_data[ADDRESS_KEY] = address.value
    await manager.switch_to(CheckoutStates.RECIPIENT)


@inject
async def on_last_address_chosen(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Reuses where the previous order went.

    The address is asked for again rather than carried in the button's data:
    what a keyboard holds is whatever was true when it was drawn, and this is
    the one field of an order that a courier acts on.
    """
    last_address = await sender.send(GetLastDeliveryAddressQuery())

    if last_address is None:
        return

    manager.dialog_data[ADDRESS_KEY] = last_address
    await manager.switch_to(CheckoutStates.RECIPIENT)


async def on_recipient_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
) -> None:
    """Splits what was typed the way the profile does: first word, then rest.

    One word means no surname rather than an error — a delivery slip reading
    "Мария" is ordinary — and ``FullName`` is built here so that the rule lives
    in one place and refuses an empty name on this screen.
    """
    typed = (message.text or "").strip()
    first_name, _, last_name = typed.partition(" ")
    name = FullName(first_name, last_name.strip() or None)

    manager.dialog_data[FIRST_NAME_KEY] = name.first_name
    manager.dialog_data[LAST_NAME_KEY] = name.last_name
    await manager.switch_to(CheckoutStates.PHONE)


async def on_recipient_is_me(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Copies the name off the profile, which is a shortcut and not a default.

    The recipient is a field of the order rather than a reference to the buyer,
    precisely because ordering something for a parent is ordinary. Copying the
    name now also means a later rename of the profile does not rewrite an order
    already placed.
    """
    user: UserView = manager.middleware_data[USER_KEY]

    manager.dialog_data[FIRST_NAME_KEY] = user.first_name
    manager.dialog_data[LAST_NAME_KEY] = user.last_name
    await manager.switch_to(CheckoutStates.PHONE)


async def on_phone_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
) -> None:
    """Normalises the number the way every other entry point does.

    ``from_raw`` and not the constructor: "8 916 123-45-67" is how a number is
    typed by hand, and the constructor accepts nothing but E.164. What gets
    stored is the canonical form, so the confirmation screen shows the number a
    manager will actually dial rather than the keystrokes.
    """
    phone_number = PhoneNumber.from_raw(message.text or "")

    manager.dialog_data[PHONE_KEY] = phone_number.value
    await manager.switch_to(CheckoutStates.COMMENT)


async def on_own_phone_chosen(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    user: UserView = manager.middleware_data[USER_KEY]

    manager.dialog_data[PHONE_KEY] = user.phone_number
    await manager.switch_to(CheckoutStates.COMMENT)


async def on_comment_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
) -> None:
    comment = OrderComment(value=(message.text or "").strip())

    manager.dialog_data[COMMENT_KEY] = comment.value
    await manager.switch_to(CheckoutStates.CONFIRM)


async def on_comment_skipped(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Leaves the order without a comment, and says so explicitly.

    Written as ``None`` rather than left unset, because somebody may have typed
    a comment, gone back and decided against it — and an unset key would keep
    the sentence they changed their mind about.
    """
    manager.dialog_data[COMMENT_KEY] = None
    await manager.switch_to(CheckoutStates.CONFIRM)


@inject
async def on_confirmed(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Places the order, and refuses to place it twice.

    ``EmptyCartError`` is caught here, and this is the only place in the
    project where a domain error is handled locally instead of being rendered
    by the one error table. The reason is that here it does not mean what it
    says. Checkout empties the cart inside the same transaction that writes the
    order, so a second tap that got past the redrawn window finds nothing to
    order — the cart is empty *because the order went through*. Showing the
    generic "your cart is empty" would be true and useless: what the person
    needs to know is that they are not about to be charged twice.

    That is also the only one of the three defences that works. Switching to
    the "placing" window takes the button away before the command is awaited,
    which loses to a tap that arrives while the first command is still inside
    its transaction; the order number in ``dialog_data`` closes a sequential
    repeat, which is the case where the redraw never reached Telegram. Neither
    survives two taps racing each other across two messengers over one shared
    cart, and an empty cart in a committed transaction does.

    Any other refusal puts the confirmation screen back before it travels on to
    the error handler. Leaving the dialog on a window with no buttons would
    turn a moved price — which the next tap would accept — into a dead end.
    """
    already_placed = placed_order_number(manager)

    if already_placed is not None:
        await _show_done(manager, already_placed, placed_order_id(manager))
        return

    await manager.switch_to(CheckoutStates.PLACING)
    await manager.show()

    try:
        placed = await sender.send(_place_order(manager))
    except EmptyCartError:
        await manager.switch_to(CheckoutStates.ALREADY_PLACED)
        return
    except AppError:
        await manager.switch_to(CheckoutStates.CONFIRM)
        await manager.show()
        raise

    order_id = str(placed.order_id)
    manager.dialog_data[ORDER_NUMBER_KEY] = placed.order_number
    manager.dialog_data[ORDER_ID_KEY] = order_id
    await _show_done(manager, placed.order_number, order_id)


def _place_order(manager: DialogManager) -> PlaceOrderCommand:
    """The order exactly as the screens before it were filled in.

    The totals come from ``dialog_data`` rather than from a fresh read, and
    that is the whole point of them: the command compares them against the cart
    it is about to sell and refuses to charge anything the customer was not
    shown.
    """
    return PlaceOrderCommand(
        delivery_address=manager.dialog_data[ADDRESS_KEY],
        recipient_first_name=manager.dialog_data[FIRST_NAME_KEY],
        recipient_last_name=manager.dialog_data.get(LAST_NAME_KEY),
        recipient_phone_number=manager.dialog_data[PHONE_KEY],
        comment=manager.dialog_data.get(COMMENT_KEY),
        expected_total=expected_total(manager),
        expected_line_count=expected_line_count(manager),
    )


async def _show_done(
    manager: DialogManager,
    number: str,
    order_id: str | None,
) -> None:
    """Opens the "done" screen on an empty stack.

    ``RESET_STACK`` rather than one more ``switch_to``, because the cart this
    dialog was started from has just been emptied by the order. A ``Cancel``
    leading back to it would offer the customer a screen saying their cart is
    empty as if that were somewhere to return to.

    Which is also why the number, the phone and the identifier travel as start
    data: everything the checkout knew is discarded with the stack, and the
    screen still has to name the order, name the number a manager will ring,
    and be able to open the order it just placed.

    ``order_id`` may be missing, and the screen copes rather than the caller
    pretending otherwise: an order placed by a build that did not record the
    identifier still has its number in ``dialog_data``, and that repeat tap
    should reach the "done" screen with one button fewer, not an exception.
    """
    data: dict[str, str] = {
        ORDER_NUMBER_KEY: number,
        ORDER_PHONE_KEY: manager.dialog_data[PHONE_KEY],
    }

    if order_id is not None:
        data[ORDER_ID_KEY] = order_id

    await manager.start(CheckoutStates.DONE, data=data, mode=StartMode.RESET_STACK)


async def on_open_order(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Opens the card of the order that was just placed.

    A callback rather than a ``Start`` widget, because the identifier is known
    only at run time and a widget's start data is fixed when the window is
    built. ``RESET_STACK`` for the same reason the "done" screen itself was
    opened that way: there is nothing underneath worth returning to.

    The orders dialog takes the identifier from its own ``on_start`` hook, so
    the key written here is the key it reads — which is why this module imports
    that constant instead of spelling the literal a second time.
    """
    started_with = manager.start_data
    order_id = started_with.get(ORDER_ID_KEY) if isinstance(started_with, dict) else None

    if not isinstance(order_id, str):
        return

    await manager.start(
        OrdersStates.CARD,
        data={ORDER_ID_KEY: order_id},
        mode=StartMode.RESET_STACK,
    )
